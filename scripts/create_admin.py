#!/usr/bin/env python3
"""
Create an admin user for the trademark system.

Usage:
    python scripts/create_admin.py admin@example.com password123
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.security import get_password_hash
from app.database import async_session_maker, init_db
from app.models import User
from app.models.user import UserRole


async def create_admin(email: str, password: str, full_name: str = None) -> None:
    """Create an admin user."""
    await init_db()

    async with async_session_maker() as session:
        # Check if user already exists
        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"User with email {email} already exists!")
            if existing.role != UserRole.ADMIN.value:
                existing.role = UserRole.ADMIN.value
                await session.commit()
                print(f"Updated {email} to admin role.")
            return

        # Create new admin user
        user = User(
            email=email,
            password_hash=get_password_hash(password),
            full_name=full_name or "Administrator",
            role=UserRole.ADMIN.value,
            is_active=True,
        )
        session.add(user)
        await session.commit()

        print(f"Admin user created successfully!")
        print(f"  Email: {email}")
        print(f"  Role: admin")


async def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/create_admin.py <email> <password> [full_name]")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]
    full_name = sys.argv[3] if len(sys.argv) > 3 else None

    await create_admin(email, password, full_name)


if __name__ == "__main__":
    asyncio.run(main())
