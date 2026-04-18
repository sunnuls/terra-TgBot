import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def check():
    e = create_async_engine(
        "postgresql+asyncpg://terra:terra@localhost:5432/terra_app", echo=False
    )
    async with e.connect() as conn:
        r = await conn.execute(
            text("SELECT id, encode(full_name::bytea, 'hex') as h FROM users")
        )
        for row in r.fetchall():
            uid, h = row
            raw = bytes.fromhex(h)
            print(f"id={uid}, stored_bytes({len(raw)})={h[:60]}...")
            # Method 1: interpret as already-utf-8 text whose bytes themselves
            # represent Latin-1 chars that should be re-decoded as UTF-8
            try:
                decoded_str = raw.decode("utf-8")  # Get the Python string stored
                # Now try to "fix" the mojibake
                refixed = decoded_str.encode("latin-1").decode("utf-8")
                print(f"  Method latin-1 -> utf-8: {refixed}")
            except Exception as ex:
                print(f"  Method latin-1 -> utf-8 FAILED: {ex}")

            try:
                # Direct utf-8 decode
                print(f"  Direct utf-8: {raw.decode('utf-8')}")
            except Exception as ex:
                print(f"  Direct utf-8 FAILED: {ex}")

    await e.dispose()


asyncio.run(check())
