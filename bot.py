import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Правильные импорты из папок
from database.db import init_db, expire_old_listings
from handlers import start, listings, meetings, reviews, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

async def main():
    # Безопасное получение токена
    token = os.getenv("BOT_TOKEN")
    if not token:
        # Резервный вариант, если забыли прописать в Railway
        token = "8879403729:AAE1ICMxtObZnG0cKN_zuLY52FpbRtYmdYw"
    
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
    dp.include_router(admin.router) # Админка первая, чтобы перехватывать команды
    dp.include_router(start.router)
    dp.include_router(listings.router)
    dp.include_router(meetings.router)
    dp.include_router(reviews.router)

    logger.info("Бот запускается...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
