# C:\bot\test_bot.py
import os, asyncio
from dotenv import load_dotenv
from aiogram import Bot

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN") or ""
print("TOKEN len =", len(TOKEN))

async def main():
    if not TOKEN:
        print("❌ Нет TELEGRAM_TOKEN в .env")
        return
    bot = Bot(TOKEN)
    me = await bot.get_me()
    print("✅ getMe:", me.id, me.username, me.first_name)
    await bot.session.close()

asyncio.run(main())
