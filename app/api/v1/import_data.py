"""Import data API endpoint - for uploading Excel files with trademark data."""

import re
import unicodedata
from datetime import date, datetime
from io import BytesIO
from typing import Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin_user
from app.database import get_db
from app.models import (
    RightsHolder,
    Territory,
    Trademark,
    TrademarkClass,
    TrademarkRegistration,
    User,
)
from app.models.trademark import RegistrationStatus, RenewalStatus

router = APIRouter()


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def parse_date(value) -> Optional[date]:
    """Parse date from various formats."""
    if pd.isna(value) or value == "нет" or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        value = value.strip()
        if value.lower() in ("нет", "no", "-", ""):
            return None
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


def parse_classes(value) -> List[int]:
    """Parse ICGS classes from comma/space separated string."""
    if pd.isna(value) or not value:
        return []
    text = str(value)
    classes = []
    for match in re.findall(r"\d+", text):
        class_num = int(match)
        if 1 <= class_num <= 45:
            classes.append(class_num)
    return sorted(set(classes))


def map_status(value: str) -> str:
    """Map Excel status values to enum values."""
    if pd.isna(value) or not value:
        return RegistrationStatus.PENDING.value

    status_lower = normalize_text(value)
    mapping = {
        "регистрация": RegistrationStatus.REGISTERED.value,
        "регисрация": RegistrationStatus.REGISTERED.value,
        "registration": RegistrationStatus.REGISTERED.value,
        "отказ": RegistrationStatus.REJECTED.value,
        "rejection": RegistrationStatus.REJECTED.value,
        "refused": RegistrationStatus.REJECTED.value,
        "частичная регистрация": RegistrationStatus.PARTIAL_REGISTRATION.value,
        "partial": RegistrationStatus.PARTIAL_REGISTRATION.value,
        "действие прекращено": RegistrationStatus.TERMINATED.value,
        "terminated": RegistrationStatus.TERMINATED.value,
        "делопроизводство": RegistrationStatus.PENDING.value,
        "pending": RegistrationStatus.PENDING.value,
        "экспертиза": RegistrationStatus.PENDING.value,
        "examination": RegistrationStatus.PENDING.value,
        "период оппозиции": RegistrationStatus.OPPOSITION.value,
        "opposition": RegistrationStatus.OPPOSITION.value,
        "решение о регистрации": RegistrationStatus.DECISION_PENDING.value,
    }

    for key, mapped_status in mapping.items():
        if key in status_lower:
            return mapped_status
    return RegistrationStatus.PENDING.value


def is_yes(value) -> bool:
    """Check if value represents 'yes'."""
    if pd.isna(value):
        return False
    return normalize_text(str(value)) in ("да", "yes", "1", "true")


def guess_region(name: str) -> str:
    """Guess region from territory name."""
    name_lower = name.lower()

    if name_lower in ("russia", "россия", "рф"):
        return "russia"
    if name_lower in ("kazakhstan", "kyrgyzstan", "armenia", "belarus", "uzbekistan",
                      "казахстан", "киргизия", "армения", "беларусь", "узбекистан"):
        return "eaeu"
    if name_lower in (
        "germany", "france", "italy", "spain", "poland", "netherlands",
        "belgium", "austria", "sweden", "norway", "finland", "denmark",
        "portugal", "greece", "czech republic", "hungary", "romania",
        "bulgaria", "croatia", "slovakia", "slovenia", "estonia",
        "latvia", "lithuania", "ireland", "luxembourg", "malta", "cyprus",
        "германия", "франция", "италия", "испания", "польша", "нидерланды"
    ):
        return "eu"
    if name_lower in ("china", "japan", "korea", "india", "vietnam", "thailand",
                      "китай", "япония", "корея", "индия", "вьетнам", "таиланд"):
        return "asia"
    if name_lower in ("united states", "usa", "canada", "mexico", "сша", "канада", "мексика"):
        return "north_america"

    return "other"


class TrademarkImporter:
    """Import trademarks from Excel to database."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.territories_cache: Dict[str, Territory] = {}
        self.rights_holders_cache: Dict[str, RightsHolder] = {}
        self.trademarks_cache: Dict[str, Trademark] = {}
        self.stats = {
            "territories_created": 0,
            "rights_holders_created": 0,
            "trademarks_created": 0,
            "registrations_created": 0,
            "classes_created": 0,
            "rows_processed": 0,
            "errors": 0,
        }

    async def get_or_create_territory(self, name: str) -> Territory:
        """Get or create territory by name."""
        name_normalized = normalize_text(name)

        if name_normalized in self.territories_cache:
            return self.territories_cache[name_normalized]

        # Check database
        result = await self.session.execute(
            select(Territory).where(
                Territory.name_en.ilike(f"%{name}%")
            )
        )
        territory = result.scalar_one_or_none()

        if not territory:
            # Also try Russian name
            result = await self.session.execute(
                select(Territory).where(
                    Territory.name_ru.ilike(f"%{name}%")
                )
            )
            territory = result.scalar_one_or_none()

        if not territory:
            territory = Territory(
                iso_code=name[:2].upper(),
                name_en=name.strip(),
                name_ru=name.strip(),
                region=guess_region(name),
            )
            self.session.add(territory)
            await self.session.flush()
            self.stats["territories_created"] += 1

        self.territories_cache[name_normalized] = territory
        return territory

    async def get_or_create_rights_holder(self, name: str) -> Optional[RightsHolder]:
        """Get or create rights holder by name."""
        if pd.isna(name) or not name:
            return None

        name_normalized = normalize_text(name)

        if name_normalized in self.rights_holders_cache:
            return self.rights_holders_cache[name_normalized]

        result = await self.session.execute(
            select(RightsHolder).where(
                RightsHolder.name_normalized == name_normalized
            )
        )
        holder = result.scalar_one_or_none()

        if not holder:
            holder = RightsHolder(
                name=name.strip(),
                name_normalized=name_normalized,
            )
            self.session.add(holder)
            await self.session.flush()
            self.stats["rights_holders_created"] += 1

        self.rights_holders_cache[name_normalized] = holder
        return holder

    async def get_or_create_trademark(
        self,
        name: str,
        rights_holder: Optional[RightsHolder],
        classes: List[int],
    ) -> Trademark:
        """Get or create trademark by name and rights holder."""
        holder_id = str(rights_holder.id) if rights_holder else "none"
        cache_key = f"{normalize_text(name)}|{holder_id}"

        if cache_key in self.trademarks_cache:
            return self.trademarks_cache[cache_key]

        trademark = Trademark(
            name=name.strip(),
            rights_holder_id=rights_holder.id if rights_holder else None,
        )
        self.session.add(trademark)
        await self.session.flush()
        self.stats["trademarks_created"] += 1

        for class_num in classes:
            tm_class = TrademarkClass(
                trademark_id=trademark.id,
                icgs_class=class_num,
            )
            self.session.add(tm_class)
            self.stats["classes_created"] += 1

        self.trademarks_cache[cache_key] = trademark
        return trademark

    async def import_row(self, row: pd.Series) -> bool:
        """Import single row from Excel."""
        try:
            # Try different column names for trademark name
            tm_name = None
            for col in ["Товарный знак (наименование)", "Товарный знак", "Наименование", "Name", "Trademark"]:
                if col in row and not pd.isna(row.get(col)):
                    tm_name = str(row.get(col)).strip()
                    if tm_name:
                        break

            if not tm_name:
                return False

            # Territory
            territory_name = "Russia"
            for col in ["Территория/страна", "Территория", "Country", "Territory"]:
                if col in row and not pd.isna(row.get(col)):
                    territory_name = str(row.get(col)).strip()
                    break

            # Classes
            classes = []
            for col in ["Классы \nМКТУ", "Классы МКТУ", "МКТУ", "Classes", "ICGS"]:
                if col in row:
                    classes = parse_classes(row.get(col))
                    if classes:
                        break

            # Rights holder
            holder_name = None
            for col in ["Правообладатель", "Owner", "Rights Holder"]:
                if col in row and not pd.isna(row.get(col)):
                    holder_name = str(row.get(col)).strip()
                    break

            # Dates
            filing_date = None
            for col in ["Дата подачи", "Filing Date"]:
                if col in row:
                    filing_date = parse_date(row.get(col))
                    if filing_date:
                        break

            priority_date = None
            for col in ["Дата Приоритета", "Дата приоритета", "Priority Date"]:
                if col in row:
                    priority_date = parse_date(row.get(col))
                    if priority_date:
                        break

            expiration_date = None
            for col in ["Cрок действия", "Срок действия", "Expiration Date", "Valid Until"]:
                if col in row:
                    expiration_date = parse_date(row.get(col))
                    if expiration_date:
                        break

            # Numbers
            application_number = None
            for col in ["Номер заявки на регистрацию", "Номер заявки", "Application Number"]:
                if col in row and not pd.isna(row.get(col)):
                    val = row.get(col)
                    if val and str(val).strip() not in ("нет", "no", "-"):
                        application_number = str(val).strip()
                        break

            registration_number = None
            for col in [" Registration Number", "Registration Number", "Номер регистрации", "Регистрационный номер"]:
                if col in row and not pd.isna(row.get(col)):
                    val = row.get(col)
                    if val and str(val).strip() not in ("нет", "no", "-"):
                        registration_number = str(val).strip()
                        break

            # Status
            status_val = RegistrationStatus.PENDING.value
            for col in ["Результат", "Status", "Статус"]:
                if col in row:
                    status_val = map_status(row.get(col))
                    break

            # Type flags
            is_national = False
            for col in ["Национальная заявка", "National"]:
                if col in row:
                    is_national = is_yes(row.get(col))
                    break

            is_international = False
            for col in ["Международная заявка", "International"]:
                if col in row:
                    is_international = is_yes(row.get(col))
                    break

            # Comments
            comments = None
            for col in ["комментарии", "Комментарии", "Comments", "Notes"]:
                if col in row and not pd.isna(row.get(col)):
                    comments = str(row.get(col)).strip()
                    break

            # Create entities
            territory = await self.get_or_create_territory(territory_name)
            rights_holder = await self.get_or_create_rights_holder(holder_name)
            trademark = await self.get_or_create_trademark(tm_name, rights_holder, classes)

            # Determine renewal status
            renewal_status = RenewalStatus.ACTIVE.value
            if status_val == RegistrationStatus.TERMINATED.value:
                renewal_status = RenewalStatus.EXPIRED.value
            elif status_val == RegistrationStatus.REJECTED.value:
                renewal_status = RenewalStatus.NOT_RENEWING.value
            elif expiration_date and expiration_date < date.today():
                renewal_status = RenewalStatus.EXPIRED.value

            registration = TrademarkRegistration(
                trademark_id=trademark.id,
                territory_id=territory.id,
                filing_date=filing_date,
                priority_date=priority_date,
                expiration_date=expiration_date,
                application_number=application_number,
                registration_number=registration_number,
                status=status_val,
                renewal_status=renewal_status,
                is_national=is_national,
                is_international=is_international,
                comments=comments,
            )
            self.session.add(registration)
            self.stats["registrations_created"] += 1
            self.stats["rows_processed"] += 1

            return True

        except Exception as e:
            self.stats["errors"] += 1
            return False

    async def import_dataframe(self, df: pd.DataFrame) -> Dict[str, int]:
        """Import entire DataFrame."""
        for idx, row in df.iterrows():
            await self.import_row(row)
            if (idx + 1) % 50 == 0:
                await self.session.flush()

        await self.session.commit()
        return self.stats


@router.post("/excel")
async def import_excel(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> Dict:
    """
    Import trademarks from Excel file.

    Only admin users can import data.
    Supported columns (in Russian or English):
    - Товарный знак / Trademark
    - Территория / Territory
    - Классы МКТУ / ICGS Classes
    - Правообладатель / Rights Holder
    - Дата подачи / Filing Date
    - Срок действия / Expiration Date
    - Номер заявки / Application Number
    - Номер регистрации / Registration Number
    - Результат / Status
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an Excel file (.xlsx or .xls)"
        )

    try:
        contents = await file.read()
        df = pd.read_excel(BytesIO(contents))

        if df.empty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Excel file is empty"
            )

        importer = TrademarkImporter(db)
        stats = await importer.import_dataframe(df)

        return {
            "success": True,
            "message": f"Successfully imported {stats['rows_processed']} records",
            "statistics": stats,
            "columns_found": list(df.columns),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )
