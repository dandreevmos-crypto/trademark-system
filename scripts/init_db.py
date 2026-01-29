#!/usr/bin/env python3
"""Initialize database: run migrations and create admin user."""

import asyncio
import os
import subprocess
import sys

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    print("=" * 50)
    print("Initializing Trademark System Database")
    print("=" * 50)

    # Run migrations
    print("\n[1/3] Running database migrations...")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Migration error: {result.stderr}")
        # If tables already exist, continue
        if "already exists" not in result.stderr:
            sys.exit(1)
    else:
        print("Migrations completed successfully!")
        if result.stdout:
            print(result.stdout)

    # Import here to avoid import errors before migrations
    from sqlalchemy import select
    from app.database import async_session_maker, engine
    from app.models.user import User
    from app.core.security import get_password_hash

    print("\n[2/3] Checking for admin user...")

    async with async_session_maker() as session:
        # Check if admin exists
        stmt = select(User).where(User.email == "admin@example.com")
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()

        if admin:
            print("Admin user already exists: admin@example.com")
        else:
            print("Creating admin user...")
            admin = User(
                email="admin@example.com",
                hashed_password=get_password_hash("admin123"),
                full_name="Administrator",
                is_active=True,
                is_superuser=True,
            )
            session.add(admin)
            await session.commit()
            print("Admin user created!")
            print("  Email: admin@example.com")
            print("  Password: admin123")
            print("  (Please change the password after first login!)")

    print("\n[3/3] Adding default territories...")

    from app.models.trademark import Territory

    async with async_session_maker() as session:
        # Check if territories exist
        stmt = select(Territory)
        result = await session.execute(stmt)
        territories = result.scalars().all()

        if territories:
            print(f"Territories already exist: {len(territories)} found")
        else:
            # Add common territories
            default_territories = [
                {"name_en": "Russia", "name_ru": "Россия", "iso_code": "RU", "region": "Europe", "fips_code": "RU"},
                {"name_en": "European Union", "name_ru": "Европейский Союз", "iso_code": "EU", "region": "Europe", "wipo_code": "EM"},
                {"name_en": "China", "name_ru": "Китай", "iso_code": "CN", "region": "Asia", "wipo_code": "CN"},
                {"name_en": "United States", "name_ru": "США", "iso_code": "US", "region": "North America", "wipo_code": "US"},
                {"name_en": "Japan", "name_ru": "Япония", "iso_code": "JP", "region": "Asia", "wipo_code": "JP"},
                {"name_en": "South Korea", "name_ru": "Южная Корея", "iso_code": "KR", "region": "Asia", "wipo_code": "KR"},
                {"name_en": "India", "name_ru": "Индия", "iso_code": "IN", "region": "Asia", "wipo_code": "IN"},
                {"name_en": "Brazil", "name_ru": "Бразилия", "iso_code": "BR", "region": "South America", "wipo_code": "BR"},
                {"name_en": "United Kingdom", "name_ru": "Великобритания", "iso_code": "GB", "region": "Europe", "wipo_code": "GB"},
                {"name_en": "Germany", "name_ru": "Германия", "iso_code": "DE", "region": "Europe", "wipo_code": "DE"},
                {"name_en": "France", "name_ru": "Франция", "iso_code": "FR", "region": "Europe", "wipo_code": "FR"},
                {"name_en": "Italy", "name_ru": "Италия", "iso_code": "IT", "region": "Europe", "wipo_code": "IT"},
                {"name_en": "Spain", "name_ru": "Испания", "iso_code": "ES", "region": "Europe", "wipo_code": "ES"},
                {"name_en": "Canada", "name_ru": "Канада", "iso_code": "CA", "region": "North America", "wipo_code": "CA"},
                {"name_en": "Australia", "name_ru": "Австралия", "iso_code": "AU", "region": "Oceania", "wipo_code": "AU"},
                {"name_en": "WIPO (International)", "name_ru": "ВОИС (Международная)", "iso_code": None, "region": "International", "wipo_code": "WO"},
            ]

            for t_data in default_territories:
                territory = Territory(**t_data)
                session.add(territory)

            await session.commit()
            print(f"Added {len(default_territories)} default territories")

    await engine.dispose()

    print("\n" + "=" * 50)
    print("Database initialization complete!")
    print("=" * 50)
    print("\nYou can now access:")
    print("  - Web UI: http://localhost:8000/static/index.html")
    print("  - API Docs: http://localhost:8000/docs")
    print("  - Login: admin@example.com / admin123")


if __name__ == "__main__":
    asyncio.run(main())
