import os, asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
assert TOKEN, "нет TELEGRAM_TOKEN/BOT_TOKEN в .env"

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()

@router.message(Command("start"))
async def start(m: Message):
    await m.answer("Я жив 👋")

dp.include_router(router)

async def main():
    print("polling…")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
