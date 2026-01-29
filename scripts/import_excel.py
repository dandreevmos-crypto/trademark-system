#!/usr/bin/env python3
"""
Import trademarks from Excel file into the database.

Usage:
    python scripts/import_excel.py path/to/excel.xlsx

This script reads the Excel file with trademark data and imports it into
the PostgreSQL database, creating all necessary related records.
"""

import asyncio
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import async_session_maker, init_db
from app.models import (
    RightsHolder,
    Territory,
    Trademark,
    TrademarkClass,
    TrademarkRegistration,
)
from app.models.trademark import RegistrationStatus, RenewalStatus


def normalize_text(text: str) -> str:
    """Normalize text for comparison (lowercase, remove extra spaces, NFKC)."""
    if not text:
        return ""
    # Normalize unicode
    text = unicodedata.normalize("NFKC", str(text))
    # Remove non-breaking spaces and other special whitespace
    text = re.sub(r"\s+", " ", text)
    # Strip and lowercase
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
        # Try different formats
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
    # Extract all numbers
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
        "регисрация": RegistrationStatus.REGISTERED.value,  # typo in data
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
            # Create new territory
            territory = Territory(
                name_en=name.strip(),
                name_ru=name.strip(),  # Same for now, can be translated later
                region=self._guess_region(name),
            )
            self.session.add(territory)
            await self.session.flush()
            self.stats["territories_created"] += 1

        self.territories_cache[name_normalized] = territory
        return territory

    def _guess_region(self, name: str) -> str:
        """Guess region from territory name."""
        name_lower = name.lower()

        if name_lower in ("russia", "россия"):
            return "russia"
        if name_lower in ("kazakhstan", "kyrgyzstan", "armenia", "belarus", "uzbekistan"):
            return "eaeu"
        if name_lower in (
            "germany", "france", "italy", "spain", "poland", "netherlands",
            "belgium", "austria", "sweden", "norway", "finland", "denmark",
            "portugal", "greece", "czech republic", "hungary", "romania",
            "bulgaria", "croatia", "slovakia", "slovenia", "estonia",
            "latvia", "lithuania", "ireland", "luxembourg", "malta", "cyprus"
        ):
            return "eu"
        if name_lower in ("china", "japan", "korea", "india", "vietnam", "thailand", "indonesia", "malaysia", "philippines", "singapore", "taiwan"):
            return "asia"
        if name_lower in ("united states", "usa", "canada", "mexico"):
            return "north_america"
        if name_lower in ("brazil", "argentina", "chile", "colombia", "peru"):
            return "south_america"
        if name_lower in ("australia", "new zealand"):
            return "oceania"
        if name_lower in ("south africa", "nigeria", "kenya", "egypt", "morocco", "ghana", "tanzania"):
            return "africa"

        return "other"

    async def get_or_create_rights_holder(self, name: str) -> RightsHolder:
        """Get or create rights holder by name."""
        if pd.isna(name) or not name:
            return None

        name_normalized = normalize_text(name)

        if name_normalized in self.rights_holders_cache:
            return self.rights_holders_cache[name_normalized]

        # Check database
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
        # Create cache key from name and holder
        holder_id = str(rights_holder.id) if rights_holder else "none"
        cache_key = f"{normalize_text(name)}|{holder_id}"

        if cache_key in self.trademarks_cache:
            return self.trademarks_cache[cache_key]

        # Create new trademark
        trademark = Trademark(
            name=name.strip(),
            rights_holder_id=rights_holder.id if rights_holder else None,
        )
        self.session.add(trademark)
        await self.session.flush()
        self.stats["trademarks_created"] += 1

        # Add classes
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
            # Parse basic data
            tm_name = str(row.get("Товарный знак (наименование)", "")).strip()
            if not tm_name:
                return False

            territory_name = str(row.get("Территория/страна", "Russia")).strip()
            classes = parse_classes(row.get("Классы \nМКТУ", ""))
            holder_name = row.get("Правообладатель")

            # Dates
            filing_date = parse_date(row.get("Дата подачи"))
            priority_date = parse_date(row.get("Дата Приоритета"))
            expiration_date = parse_date(row.get("Cрок действия"))

            # Numbers
            application_number = row.get("Номер заявки на регистрацию")
            if pd.isna(application_number):
                application_number = None
            else:
                application_number = str(application_number).strip()

            registration_number = row.get(" Registration Number")  # Note: leading space in column name
            if pd.isna(registration_number) or registration_number == "нет":
                registration_number = None
            else:
                registration_number = str(registration_number).strip()

            # Status
            status = map_status(row.get("Результат", ""))

            # Type flags
            is_national = is_yes(row.get("Национальная заявка"))
            is_international = is_yes(row.get("Международная заявка"))

            # Comments
            comments = row.get("комментарии")
            if pd.isna(comments):
                comments = None

            # Get/create related entities
            territory = await self.get_or_create_territory(territory_name)
            rights_holder = await self.get_or_create_rights_holder(holder_name) if holder_name else None
            trademark = await self.get_or_create_trademark(tm_name, rights_holder, classes)

            # Determine renewal status
            renewal_status = RenewalStatus.ACTIVE.value
            if status == RegistrationStatus.TERMINATED.value:
                renewal_status = RenewalStatus.EXPIRED.value
            elif status == RegistrationStatus.REJECTED.value:
                renewal_status = RenewalStatus.NOT_RENEWING.value
            elif expiration_date and expiration_date < date.today():
                renewal_status = RenewalStatus.EXPIRED.value

            # Create registration
            registration = TrademarkRegistration(
                trademark_id=trademark.id,
                territory_id=territory.id,
                filing_date=filing_date,
                priority_date=priority_date,
                expiration_date=expiration_date,
                application_number=application_number,
                registration_number=registration_number,
                status=status,
                renewal_status=renewal_status,
                is_national=is_national,
                is_international=is_international,
                comments=comments,
            )
            self.session.add(registration)
            self.stats["registrations_created"] += 1

            return True

        except Exception as e:
            print(f"Error importing row: {e}")
            self.stats["errors"] += 1
            return False

    async def import_file(self, file_path: str) -> Dict[str, int]:
        """Import entire Excel file."""
        print(f"Reading Excel file: {file_path}")
        df = pd.read_excel(file_path)

        print(f"Found {len(df)} rows")

        for idx, row in df.iterrows():
            if await self.import_row(row):
                if (idx + 1) % 100 == 0:
                    print(f"Processed {idx + 1} rows...")
                    await self.session.flush()

        await self.session.commit()

        print("\n=== Import Statistics ===")
        for key, value in self.stats.items():
            print(f"{key}: {value}")

        return self.stats


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_excel.py path/to/excel.xlsx")
        sys.exit(1)

    file_path = sys.argv[1]
    if not Path(file_path).exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    # Initialize database
    print("Initializing database...")
    await init_db()

    # Import data
    async with async_session_maker() as session:
        importer = TrademarkImporter(session)
        await importer.import_file(file_path)

    print("\nImport completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
