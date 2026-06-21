import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Правильные импорты из папок
from database.db import init_db, expire_old_listings
from handlers import start, listings, meetings, reviews

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

async def main():
    # Используем токен напрямую для Railway, если переменная окружения не задана
    token = os.getenv("BOT_TOKEN", "8879403729:AAHFhV7kIzULCF17vH3IgijSqiXWM6gDqJU")
    
    # Инициализация БД
    await init_db()
    logger.info("База данных инициализирована.")

    # Планировщик
    scheduler = AsyncIOScheduler()
    scheduler.add_job(expire_old_listings, "interval", minutes=15)
    scheduler.start()

    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация роутеров
    dp.include_router(start.router)
    dp.include_router(listings.router)
    dp.include_router(meetings.router)
    dp.include_router(reviews.router)

    logger.info("Бот запускается...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
