"""
CLI-утилиты для управления приложением.
Использование:
    python -m app.cli create-admin --email admin@example.com --password secret
"""
import argparse
import asyncio
import sys

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.core.security import hash_password
from app.core.uuid7 import uuid7_str


async def create_admin(email: str, password: str, username: str) -> None:
    async with AsyncSessionLocal() as session:
        # Проверить — не существует ли уже такой email
        existing = await session.scalar(select(User).where(User.email == email))
        if existing:
            print(f"[ERROR] Пользователь с email '{email}' уже существует.")
            sys.exit(1)

        user = User(
            id=uuid7_str(),
            email=email,
            username=username,
            hashed_password=hash_password(password),
            role=UserRole.admin,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        print(f"[OK] Администратор создан: {email} (username: {username})")


def main() -> None:
    parser = argparse.ArgumentParser(description="DAST CLI")
    subparsers = parser.add_subparsers(dest="command")

    # create-admin
    p = subparsers.add_parser("create-admin", help="Создать администратора")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--username", default=None, help="Если не указан — берётся из email до @")

    args = parser.parse_args()

    if args.command == "create-admin":
        username = args.username or args.email.split("@")[0]
        asyncio.run(create_admin(args.email, args.password, username))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
