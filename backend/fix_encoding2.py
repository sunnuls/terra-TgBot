"""Fix double-encoded names: 54 bytes -> 26 bytes (proper UTF-8)."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def fix():
    e = create_async_engine(
        "postgresql+asyncpg://terra:terra@localhost:5432/terra_app", echo=False
    )
    async with e.connect() as conn:
        # Get raw bytes and try to recover correct string
        r = await conn.execute(
            text("SELECT id, encode(full_name::bytea, 'hex') as h FROM users")
        )
        rows = r.fetchall()

        for uid, h in rows:
            raw = bytes.fromhex(h)
            if len(raw) <= 30:
                print(f"id={uid}: already OK ({len(raw)} bytes), skipping")
                continue

            # The bytes ARE valid UTF-8 encoding of wrong string.
            # The wrong string is UTF-8-encoded-Latin-1 mojibake.
            # To fix: decode UTF-8 to get mojibake string,
            # then encode each char as latin-1 byte, decode result as UTF-8
            try:
                mojibake = raw.decode("utf-8")
                # Each char in mojibake came from encoding a byte as UTF-8
                # reverse: encode chars as cp1252 bytes, decode as UTF-8
                fixed_bytes = mojibake.encode("cp1252")
                fixed_str = fixed_bytes.decode("utf-8")
                print(f"id={uid}: fixed '{fixed_str}' ({len(fixed_str.encode('utf-8'))} bytes)")
                await conn.execute(
                    text("UPDATE users SET full_name = :name WHERE id = :id"),
                    {"name": fixed_str, "id": uid}
                )
            except Exception as ex:
                print(f"id={uid}: cp1252 failed ({ex}), trying raw_unicode_escape")
                try:
                    mojibake = raw.decode("utf-8")
                    fixed_str = mojibake.encode("raw_unicode_escape").decode("utf-8")
                    print(f"  -> '{fixed_str}'")
                    await conn.execute(
                        text("UPDATE users SET full_name = :name WHERE id = :id"),
                        {"name": fixed_str, "id": uid}
                    )
                except Exception as ex2:
                    print(f"  -> FAILED: {ex2}")

        await conn.commit()
        print("\nVerification:")
        r2 = await conn.execute(
            text("SELECT id, full_name, octet_length(full_name) FROM users")
        )
        for row in r2.fetchall():
            print(f"  id={row[0]}, bytes={row[2]}, name={row[1]!r}")

    await e.dispose()


asyncio.run(fix())
