import asyncio
from html import escape

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import (
    admin_ban_user as db_admin_ban_user,
    admin_counts,
    admin_list_listings,
    admin_list_users,
    admin_user_ids,
    close_listing,
    get_listing,
)

router = Router()

# Главный администратор бота.
ADMIN_IDS = [683764730]


class AdminStates(StatesGroup):
    waiting_listing_id = State()
    waiting_broadcast_text = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📣 Активные публикации", callback_data="admin_listings")],
        [InlineKeyboardButton(text="📋 Проверить по ID", callback_data="admin_check_listing")],
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_users_list")],
        [InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="admin_broadcast")],
    ])


def short(value, limit=180):
    text = escape(str(value or ""))
    return text if len(text) <= limit else text[:limit - 1] + "…"


def listing_author(row):
    name = short(row.get("first_name") or "Без имени", 60)
    username = row.get("username")
    return f"@{short(username, 50)}" if username else f'<a href="tg://user?id={row["user_id"]}">{name}</a>'


async def send_listing(message, listing):
    listing_id = listing["id"]
    text = (
        f"🆔 <b>Публикация #{listing_id}</b>\n"
        f"👤 Автор: {listing_author(listing)} (ID: <code>{listing['user_id']}</code>)\n"
        f"📌 <b>{short(listing.get('title'), 120)}</b>\n"
        f"📝 {short(listing.get('description'), 500)}\n"
        f"🍾 {short(listing.get('drinks'), 160)}\n"
        f"🥨 {short(listing.get('snacks'), 160)}\n"
        f"📍 {short(listing.get('location_name'), 100)}\n"
        f"📅 Статус: <b>{short(listing.get('status'), 30)}</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить публикацию", callback_data=f"admin_del:{listing_id}")],
        [InlineKeyboardButton(text="🔨 Забанить автора", callback_data=f"admin_ban:{listing['user_id']}")],
        [InlineKeyboardButton(text="⬅️ К списку публикаций", callback_data="admin_listings")],
    ])
    try:
        if listing.get("photo_id"):
            await message.answer_photo(listing["photo_id"], caption=text, parse_mode="HTML", reply_markup=kb)
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    users_count, active_listings = await admin_counts()
    await message.answer(
        f"🛠 <b>Главная админ-панель</b>\n\n"
        f"👥 Пользователей: {users_count}\n"
        f"🍻 Активных публикаций: {active_listings}\n\n"
        "Здесь можно просматривать и удалять публикации, банить нарушителей и делать рассылку.",
        parse_mode="HTML", reply_markup=admin_kb()
    )


@router.callback_query(F.data == "admin_listings")
async def admin_listings(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    rows = await admin_list_listings()
    if not rows:
        await callback.message.answer("📣 Активных публикаций пока нет.", reply_markup=admin_kb())
        await callback.answer()
        return

    text = "📣 <b>Активные публикации</b> (последние 30):\n\n"
    buttons = []
    for row in rows:
        text += (
            f"🆔 <b>#{row['id']}</b> — {short(row.get('title'), 80)}\n"
            f"👤 {listing_author(row)} (ID: <code>{row['user_id']}</code>)\n"
            f"📍 {short(row.get('location_name'), 60)}\n\n"
        )
        buttons.append([InlineKeyboardButton(
            text=f"Открыть #{row['id']} — {short(row.get('title'), 35)}",
            callback_data=f"admin_show:{row['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ В админ-панель", callback_data="admin_back")])
    await callback.message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_show:"))
async def admin_show_listing(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    listing_id = int(callback.data.split(":", 1)[1])
    listing = await get_listing(listing_id)
    if not listing:
        await callback.answer("Публикация не найдена", show_alert=True)
        return
    await send_listing(callback.message, listing)
    await callback.answer()


@router.callback_query(F.data == "admin_check_listing")
async def admin_check_listing_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.answer("Введи ID публикации для проверки:")
    await state.set_state(AdminStates.waiting_listing_id)
    await callback.answer()


@router.message(AdminStates.waiting_listing_id)
async def admin_process_listing_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        listing_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введи числовой ID публикации.")
        return
    listing = await get_listing(listing_id)
    if not listing:
        await message.answer("Публикация не найдена.")
    else:
        await send_listing(message, listing)
    await state.clear()


@router.callback_query(F.data.startswith("admin_del:"))
async def admin_delete_listing(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    listing_id = int(callback.data.split(":", 1)[1])
    await close_listing(listing_id)
    await callback.message.answer(f"✅ Публикация #{listing_id} закрыта и больше не показывается пользователям.")
    await callback.answer("Удалено")


@router.callback_query(F.data.startswith("admin_ban:"))
async def admin_ban_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":", 1)[1])
    if user_id in ADMIN_IDS:
        await callback.answer("Нельзя забанить администратора", show_alert=True)
        return
    await db_admin_ban_user(user_id)
    await callback.message.answer(f"🔨 Пользователь {user_id} забанен.")
    await callback.answer("Пользователь заблокирован")


@router.callback_query(F.data == "admin_users_list")
async def admin_users_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    rows = await admin_list_users(limit=30)
    text = "👥 <b>Последние пользователи</b> (до 30):\n"
    if not rows:
        text += "\nПока никто не зарегистрирован."
    for row in rows:
        name = short(row.get("first_name") or "Без имени", 60)
        link = f"@{short(row['username'], 50)}" if row.get("username") else f'<a href="tg://user?id={row["id"]}">{name}</a>'
        text += f"\n<code>{row['id']}</code> — {link}"
    await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_kb())
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.answer("Введи текст для рассылки всем пользователям:")
    await state.set_state(AdminStates.waiting_broadcast_text)
    await callback.answer()


@router.message(AdminStates.waiting_broadcast_text)
async def admin_broadcast_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    users = await admin_user_ids()
    count = 0
    for user_id in users:
        try:
            await message.bot.send_message(user_id, f"📢 <b>Объявление от админа:</b>\n\n{escape(text)}", parse_mode="HTML")
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await message.answer(f"✅ Рассылка завершена. Получили {count} чел.")
    await state.clear()


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    users_count, active_listings = await admin_counts()
    await callback.message.answer(
        f"🛠 <b>Главная админ-панель</b>\n\n👥 Пользователей: {users_count}\n🍻 Активных публикаций: {active_listings}",
        parse_mode="HTML", reply_markup=admin_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_close")
async def admin_close(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()
