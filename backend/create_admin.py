"""
Utility: create the first admin user.
Run: python create_admin.py --login admin --password YourPass123 --name "Admin Name"
"""
import asyncio
import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User, AuthCredential, UserRole
from sqlalchemy import select


async def create_admin(login: str, password: str, name: str):
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(AuthCredential).where(AuthCredential.login == login))
        if existing.scalar_one_or_none():
            print(f"Login '{login}' already exists!")
            return

        user = User(full_name=name)
        db.add(user)
        await db.flush()

        db.add(AuthCredential(user_id=user.id, login=login, password_hash=hash_password(password)))
        db.add(UserRole(user_id=user.id, role="admin"))
        await db.commit()
        await db.refresh(user)
        print(f"Admin created: ID={user.id}, login={login}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--name", default="Администратор")
    args = parser.parse_args()
    asyncio.run(create_admin(args.login, args.password, args.name))
