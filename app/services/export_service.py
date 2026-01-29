"""Service for exporting trademarks to Excel."""

import io
from datetime import date
from typing import List, Optional
from uuid import UUID

import xlsxwriter
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Trademark, TrademarkRegistration, TrademarkClass
from app.models.trademark import RenewalStatus, RegistrationStatus
from app.schemas.trademark import TrademarkExportFilters


# Column definitions for export
EXPORT_COLUMNS = [
    ("trademark_name", "Товарный знак", 30),
    ("description", "Описание", 40),
    ("rights_holder", "Правообладатель", 35),
    ("territory", "Территория", 20),
    ("icgs_classes", "Классы МКТУ", 15),
    ("product_groups", "Группы товаров", 25),
    ("application_number", "Номер заявки", 20),
    ("registration_number", "Номер регистрации", 20),
    ("filing_date", "Дата подачи", 15),
    ("priority_date", "Дата приоритета", 15),
    ("expiration_date", "Срок действия", 15),
    ("status", "Статус", 20),
    ("renewal_status", "Статус продления", 20),
    ("is_national", "Национальная", 12),
    ("is_international", "Международная", 12),
    ("comments", "Комментарии", 40),
]

# Status translations
STATUS_TRANSLATIONS = {
    RegistrationStatus.PENDING.value: "Делопроизводство",
    RegistrationStatus.OPPOSITION.value: "Период оппозиции",
    RegistrationStatus.REGISTERED.value: "Регистрация",
    RegistrationStatus.PARTIAL_REGISTRATION.value: "Частичная регистрация",
    RegistrationStatus.REJECTED.value: "Отказ",
    RegistrationStatus.TERMINATED.value: "Действие прекращено",
    RegistrationStatus.DECISION_PENDING.value: "Решение о регистрации",
}

RENEWAL_STATUS_TRANSLATIONS = {
    RenewalStatus.ACTIVE.value: "Активен",
    RenewalStatus.RENEWAL_FILED.value: "Продление подано",
    RenewalStatus.NOT_RENEWING.value: "Решено не продлевать",
    RenewalStatus.EXPIRED.value: "Истёк",
}


class ExportService:
    """Service for exporting trademark data."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def export_to_excel(
        self,
        filters: Optional[TrademarkExportFilters] = None,
    ) -> bytes:
        """
        Export trademarks to Excel based on filters.

        Returns bytes of the Excel file.
        """
        # Get filtered data
        registrations = await self._get_filtered_registrations(filters)

        # Create Excel file
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Товарные знаки")

        # Define formats
        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#4472C4",
            "font_color": "white",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
            "text_wrap": True,
        })

        date_format = workbook.add_format({
            "num_format": "dd.mm.yyyy",
            "border": 1,
        })

        cell_format = workbook.add_format({
            "border": 1,
            "valign": "vcenter",
            "text_wrap": True,
        })

        # Write headers
        for col, (key, title, width) in enumerate(EXPORT_COLUMNS):
            worksheet.write(0, col, title, header_format)
            worksheet.set_column(col, col, width)

        # Freeze header row
        worksheet.freeze_panes(1, 0)

        # Write data
        for row_num, registration in enumerate(registrations, start=1):
            row_data = self._extract_row_data(registration)

            for col, (key, _, _) in enumerate(EXPORT_COLUMNS):
                value = row_data.get(key)

                if key.endswith("_date") and value:
                    worksheet.write(row_num, col, value, date_format)
                else:
                    worksheet.write(row_num, col, value or "", cell_format)

        # Add autofilter
        if registrations:
            worksheet.autofilter(0, 0, len(registrations), len(EXPORT_COLUMNS) - 1)

        workbook.close()
        output.seek(0)
        return output.getvalue()

    async def _get_filtered_registrations(
        self,
        filters: Optional[TrademarkExportFilters],
    ) -> List[TrademarkRegistration]:
        """Get registrations based on filters."""
        query = (
            select(TrademarkRegistration)
            .options(
                selectinload(TrademarkRegistration.trademark).selectinload(Trademark.rights_holder),
                selectinload(TrademarkRegistration.trademark).selectinload(Trademark.classes),
                selectinload(TrademarkRegistration.territory),
            )
        )

        if filters:
            conditions = []

            # Rights holder filter
            if filters.rights_holder_ids:
                query = query.join(Trademark).where(
                    Trademark.rights_holder_id.in_(filters.rights_holder_ids)
                )

            # Territory filter
            if filters.territory_ids:
                conditions.append(
                    TrademarkRegistration.territory_id.in_(filters.territory_ids)
                )

            # ICGS class filter
            if filters.icgs_classes:
                query = query.join(TrademarkRegistration.trademark).join(Trademark.classes).where(
                    TrademarkClass.icgs_class.in_(filters.icgs_classes)
                )

            # Product group filter
            if filters.product_groups:
                if not filters.icgs_classes:
                    query = query.join(TrademarkRegistration.trademark).join(Trademark.classes)
                query = query.where(
                    TrademarkClass.product_group.in_(filters.product_groups)
                )

            # Status filter
            if filters.statuses:
                conditions.append(
                    TrademarkRegistration.status.in_(filters.statuses)
                )

            # Renewal status filter
            if filters.renewal_statuses:
                conditions.append(
                    TrademarkRegistration.renewal_status.in_(filters.renewal_statuses)
                )

            # Expiration date range
            if filters.expiration_from:
                conditions.append(
                    TrademarkRegistration.expiration_date >= filters.expiration_from
                )
            if filters.expiration_to:
                conditions.append(
                    TrademarkRegistration.expiration_date <= filters.expiration_to
                )

            # Exclude expired unless requested
            if not filters.include_expired:
                conditions.append(
                    TrademarkRegistration.renewal_status != RenewalStatus.EXPIRED.value
                )

            # Exclude rejected unless requested
            if not filters.include_rejected:
                conditions.append(
                    TrademarkRegistration.status != RegistrationStatus.REJECTED.value
                )

            if conditions:
                query = query.where(and_(*conditions))

        query = query.order_by(
            TrademarkRegistration.expiration_date.asc().nulls_last()
        )

        result = await self.session.execute(query)
        return result.scalars().unique().all()

    def _extract_row_data(self, registration: TrademarkRegistration) -> dict:
        """Extract data for a single row."""
        trademark = registration.trademark
        territory = registration.territory

        # Get classes
        classes = sorted([c.icgs_class for c in trademark.classes]) if trademark.classes else []
        classes_str = ", ".join(map(str, classes))

        # Get product groups
        product_groups = set()
        for c in trademark.classes or []:
            if c.product_group:
                product_groups.add(c.product_group)
        product_groups_str = ", ".join(sorted(product_groups))

        # Get rights holder
        rights_holder = trademark.rights_holder.name if trademark.rights_holder else ""

        return {
            "trademark_name": trademark.name,
            "description": trademark.description,
            "rights_holder": rights_holder,
            "territory": territory.name_ru if territory else "",
            "icgs_classes": classes_str,
            "product_groups": product_groups_str,
            "application_number": registration.application_number,
            "registration_number": registration.registration_number,
            "filing_date": registration.filing_date,
            "priority_date": registration.priority_date,
            "expiration_date": registration.expiration_date,
            "status": STATUS_TRANSLATIONS.get(registration.status, registration.status),
            "renewal_status": RENEWAL_STATUS_TRANSLATIONS.get(
                registration.renewal_status, registration.renewal_status
            ),
            "is_national": "Да" if registration.is_national else "Нет",
            "is_international": "Да" if registration.is_international else "Нет",
            "comments": registration.comments,
        }
