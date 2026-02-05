#!/usr/bin/env python3
"""Seed script to create an admin user."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.security import hash_password
from app.database import async_session_maker
from app.models.user import User


async def create_admin_user(
    email: str = "admin@nikoh.com",
    password: str = "admin123",
    phone: str | None = None,
) -> None:
    """Create an admin user if it doesn't exist."""
    async with async_session_maker() as db:
        # Check if admin already exists
        result = await db.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            if existing_user.is_admin:
                print(f"Admin user already exists: {email}")
            else:
                # Upgrade to admin
                existing_user.is_admin = True
                await db.commit()
                print(f"Upgraded existing user to admin: {email}")
            return

        # Create new admin user
        admin = User(
            email=email,
            password_hash=hash_password(password),
            phone=phone,
            is_admin=True,
            email_verified=True,
            status="active",
            verification_status="verified",
        )
        db.add(admin)
        await db.commit()
        print(f"Created admin user: {email}")
        print(f"Password: {password}")
        print("\nYou can now login with these credentials.")


async def make_user_admin(email: str) -> None:
    """Make an existing user an admin."""
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            print(f"User not found: {email}")
            return

        if user.is_admin:
            print(f"User is already an admin: {email}")
            return

        user.is_admin = True
        await db.commit()
        print(f"Made user admin: {email}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Admin user seeder")
    parser.add_argument(
        "--email",
        default="admin@nikoh.com",
        help="Admin email (default: admin@nikoh.com)",
    )
    parser.add_argument(
        "--password",
        default="admin123",
        help="Admin password (default: admin123)",
    )
    parser.add_argument(
        "--phone",
        default=None,
        help="Admin phone number (optional)",
    )
    parser.add_argument(
        "--make-admin",
        metavar="EMAIL",
        help="Make an existing user an admin by email",
    )

    args = parser.parse_args()

    if args.make_admin:
        asyncio.run(make_user_admin(args.make_admin))
    else:
        asyncio.run(create_admin_user(args.email, args.password, args.phone))


if __name__ == "__main__":
    main()
