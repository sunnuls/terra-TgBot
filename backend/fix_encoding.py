"""Fix double-encoded UTF-8 names in the database."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
import os

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://terra:terra@localhost:5432/terra_app"
)


def try_fix_encoding(s: str) -> str:
    """Try to fix double-encoded UTF-8 string."""
    try:
        fixed = s.encode("raw_unicode_escape").decode("utf-8")
        if fixed and any(ord(c) > 127 for c in fixed):
            return fixed
    except Exception:
        pass
    try:
        fixed = s.encode("latin-1").decode("utf-8")
        return fixed
    except Exception:
        pass
    return s


async def fix():
    engine = create_async_engine(DB_URL, echo=False)
    async with AsyncSession(engine) as db:
        result = await db.execute(text("SELECT id, full_name FROM users"))
        rows = result.fetchall()
        fixed_count = 0
        for row in rows:
            uid, name = row
            if name:
                fixed = try_fix_encoding(name)
                if fixed != name:
                    await db.execute(
                        text("UPDATE users SET full_name = :name WHERE id = :id"),
                        {"name": fixed, "id": uid}
                    )
                    print(f"  Fixed user id={uid}: '{name}' -> '{fixed}'")
                    fixed_count += 1
                else:
                    print(f"  User id={uid}: '{name}' (ok)")
        await db.commit()
        print(f"\nFixed {fixed_count} users.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(fix())
