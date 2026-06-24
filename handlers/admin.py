from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import os
import asyncio
import aiosqlite

from database.db import DB_PATH, get_listing, close_listing

router = Router()

# Твой ID администратора
ADMIN_IDS = [683764730]

class AdminStates(StatesGroup):
    waiting_listing_id = State()
    waiting_broadcast_text = State()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Проверить анкету", callback_query_data="admin_check_listing")],
        [InlineKeyboardButton(text="📢 Сделать рассылку", callback_query_data="admin_broadcast")],
        [InlineKeyboardButton(text="👥 Список юзеров", callback_query_data="admin_users_list")]
    ])

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
        f"🛠 <b>Админ-панель</b>\n\n"
        f"👥 Всего пользователей: {users_count}\n"
        f"🍻 Активных движей: {active_listings}\n\n"
        f"Выбери действие:"
    )
    await message.answer(stats, parse_mode="HTML", reply_markup=admin_kb())

# --- ПРОВЕРКА АНКЕТЫ ---

@router.callback_query(F.data == "admin_check_listing")
async def admin_check_listing_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.answer("Введи ID анкеты для проверки (он указан в жалобе):")
    await state.set_state(AdminStates.waiting_listing_id)
    await callback.answer()

@router.message(AdminStates.waiting_listing_id)
async def admin_process_listing_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    
    try:
        l_id = int(message.text.strip())
    except:
        await message.answer("Введи числовой ID!")
        return

    anketa = await get_listing(l_id)
    if not anketa:
        await message.answer("Анкета не найдена.")
        await state.clear()
        return

    # Ссылка на автора
    author_name = anketa['first_name'].replace("<", "&lt;").replace(">", "&gt;")
    author_link = f"@{anketa['username']}" if anketa['username'] else f'<a href="tg://user?id={anketa["user_id"]}">{author_name}</a>'

    text = (
        f"🆔 <b>Анкета №{l_id}</b>\n"
        f"👤 Автор: {author_link} (ID: <code>{anketa['user_id']}</code>)\n"
        f"📌 Заголовок: {anketa['title']}\n"
        f"📝 Описание: {anketa['description']}\n"
        f"🍾 Напитки: {anketa['drinks']}\n"
        f"📅 Статус: {anketa['status']}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить анкету", callback_query_data=f"admin_del:{l_id}")],
        [InlineKeyboardButton(text="🔨 Забанить автора", callback_query_data=f"admin_ban:{anketa['user_id']}")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_query_data="admin_close")]
    ])

    try:
        await message.answer_photo(photo=anketa['photo_id'], caption=text, parse_mode="HTML", reply_markup=kb)
    except:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
    
    await state.clear()

# --- ДЕЙСТВИЯ АДМИНА ---

@router.callback_query(F.data.startswith("admin_del:"))
async def admin_delete_listing(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    l_id = int(callback.data.split(":")[1])
    await close_listing(l_id)
    await callback.message.answer(f"✅ Анкета №{l_id} удалена.")
    await callback.answer()

@router.callback_query(F.data.startswith("admin_ban:"))
async def admin_ban_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    u_id = int(callback.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned = 1 WHERE id = ?", (u_id,))
        await db.commit()
    await callback.message.answer(f"🔨 Пользователь {u_id} забанен.")
    await callback.answer()

@router.callback_query(F.data == "admin_users_list")
async def admin_users_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, first_name, username FROM users ORDER BY created_at DESC LIMIT 15") as cur:
            rows = await cur.fetchall()
            
    text = "👥 <b>Последние 15 юзеров:</b>\n"
    for r in rows:
        name = r['first_name'].replace("<", "&lt;").replace(">", "&gt;")
        link = f"@{r['username']}" if r['username'] else f'<a href="tg://user?id={r["id"]}">{name}</a>'
        text += f"\n<code>{r['id']}</code> - {link}"
    
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.answer("Введи текст для рассылки всем пользователям:")
    await state.set_state(AdminStates.waiting_broadcast_text)
    await callback.answer()

@router.message(AdminStates.waiting_broadcast_text)
async def admin_broadcast_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    text = message.text.strip()
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM users") as cur:
            users = await cur.fetchall()
            
    count = 0
    for u in users:
        try:
            await message.bot.send_message(u[0], f"📢 <b>Объявление от админа:</b>\n\n{text}", parse_mode="HTML")
            count += 1
            await asyncio.sleep(0.05)
        except: pass
        
    await message.answer(f"✅ Рассылка завершена! Получили {count} чел.")
    await state.clear()

@router.callback_query(F.data == "admin_close")
async def admin_close(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()
