from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import os

from database.db import DB_PATH
import aiosqlite

router = Router()

# Твой ID. Я пропишу его как список, можно будет добавить еще админов.
ADMIN_IDS = [8879403729, 642848466] # Я добавил ID из твоего токена и примерный. Замени на свой!

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            users_count = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM listings WHERE status = 'active'") as cur:
            active_listings = (await cur.fetchone())[0]

    stats = (
        f"🛠 *Админ-панель*\n\n"
        f"👥 Всего пользователей: {users_count}\n"
        f"🍻 Активных движей: {active_listings}\n\n"
        f"Команды:\n"
        f"/users - список пользователей\n"
        f"/ban <id> - забанить\n"
        f"/broadcast <текст> - рассылка всем"
    )
    await message.answer(stats, parse_mode="Markdown")

@router.message(Command("users"))
async def cmd_users(message: Message):
    if not is_admin(message.from_user.id): return
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, first_name, username FROM users LIMIT 20") as cur:
            rows = await cur.fetchall()
            
    text = "👥 *Последние 20 юзеров:*\n"
    for r in rows:
        text += f"\n`{r['id']}` - {r['first_name']} (@{r['username'] or 'no'})"
    
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id): return
    
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("Введи текст рассылки!")
        return
        
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM users") as cur:
            users = await cur.fetchall()
            
    count = 0
    for u in users:
        try:
            await message.bot.send_message(u[0], f"📢 *Объявление от админа:*\n\n{text}", parse_mode="Markdown")
            count += 1
            await asyncio.sleep(0.05) # Защита от спам-фильтра
        except: pass
        
    await message.answer(f"✅ Рассылка завершена! Получили {count} чел.")
