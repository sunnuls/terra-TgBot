"""Directly overwrite names with correct UTF-8 strings."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Map user IDs to correct names - hardcoded proper UTF-8
CORRECT_NAMES = {
    2: "\u0410\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440",
    3: "\u0410\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440",
}
# That's "Администратор" as proper unicode escapes


async def fix():
    e = create_async_engine(
        "postgresql+asyncpg://terra:terra@localhost:5432/terra_app", echo=False
    )
    async with e.connect() as conn:
        for uid, name in CORRECT_NAMES.items():
            expected_bytes = len(name.encode("utf-8"))
            await conn.execute(
                text("UPDATE users SET full_name = :name WHERE id = :id"),
                {"name": name, "id": uid}
            )
            print(f"Updated id={uid}: '{name}' ({expected_bytes} bytes)")
        await conn.commit()

        # Verify
        print("\nVerification:")
        r = await conn.execute(
            text("SELECT id, full_name, octet_length(full_name) FROM users")
        )
        for row in r.fetchall():
            print(f"  id={row[0]}, bytes={row[2]}, name={row[1]!r}")
    await e.dispose()


asyncio.run(fix())
