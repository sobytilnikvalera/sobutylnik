import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database.db import init_db, expire_old_listings
from handlers import start, listings, meetings, reviews

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError(
            "BOT_TOKEN не найден! Создай файл .env с BOT_TOKEN=<твой_токен>"
        )

    # Инициализация БД
    await init_db()
    logger.info("База данных инициализирована.")

    # Планировщик для автоматического истечения объявлений
    scheduler = AsyncIOScheduler()
    scheduler.add_job(expire_old_listings, "interval", minutes=15)
    scheduler.start()
    logger.info("Планировщик запущен (проверка истечения каждые 15 минут).")

    # Создание бота и диспетчера
    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация роутеров
    dp.include_router(start.router)
    dp.include_router(listings.router)
    dp.include_router(meetings.router)
    dp.include_router(reviews.router)

    logger.info("Бот запускается...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
