import asyncio
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


class HealthHandler(BaseHTTPRequestHandler):
    """Minimal HTTP endpoint required by Render Web Services."""

    def do_GET(self):
        if self.path in ("/", "/health"):
            body = b"sobutylnik is running\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        # Keep routine health checks out of the bot logs.
        return


def start_health_server():
    """Expose a lightweight health endpoint for Render and external monitoring."""
    port = int(os.getenv("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health server listening on port %s", port)
    return server

async def main():
    # Безопасное получение токена
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("КРИТИЧЕСКАЯ ОШИБКА: Переменная BOT_TOKEN не найдена в окружении!")
        return
    
    # Инициализация БД
    await init_db()
    logger.info("База данных инициализирована.")

    # Планировщик
    scheduler = AsyncIOScheduler()
    scheduler.add_job(expire_old_listings, "interval", minutes=15)
    scheduler.start()

    # Render Web Services require a listening HTTP port.
    health_server = start_health_server()

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
        health_server.shutdown()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
