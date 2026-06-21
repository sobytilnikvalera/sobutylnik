from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database.db import (
    get_user, create_listing, get_listing,
    get_active_listings_near, get_user_listings, close_listing
)
from states.states import CreateListing
from utils.keyboards import (
    main_menu_kb, location_kb, cancel_kb, confirm_kb,
    listing_actions_kb, listings_nav_kb, skip_kb
)
from utils.helpers import format_listing, filter_by_radius

router = Router()

# ─── СОЗДАНИЕ ОБЪЯВЛЕНИЯ ──────────────────────────────────────────────────────

@router.message(F.text == "📢 Создать объявление")
@router.message(Command("post"))
async def cmd_create_listing(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйся — нажми /start")
        return

    await state.clear()
    await message.answer(
        "📢 *Создание объявления*\n\n"
        "Шаг 1/6 — Придумай заголовок объявления.\n"
        "Например: «Виски + пиво, ищу компанию» или «Есть вино и сыр»",
        parse_mode="Markdown",
        reply_markup=cancel_kb()
    )
    await state.set_state(CreateListing.waiting_title)


@router.message(CreateListing.waiting_title)
async def process_title(message: Message, state: FSMContext):
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Создание отменено.", reply_markup=main_menu_kb())
        return

    title = message.text.strip()[:100]
    if len(title) < 3:
        await message.answer("Заголовок слишком короткий. Попробуй ещё раз.")
        return

    await state.update_data(title=title)
    await message.answer(
        "Шаг 2/6 — Опиши ситуацию подробнее.\n"
        "Например: «Сижу дома, скучно. Готов принять гостей или выйти во двор»\n"
        "(или нажми «Пропустить»)",
        reply_markup=skip_kb()
    )
    await state.set_state(CreateListing.waiting_description)


@router.message(CreateListing.waiting_description)
async def process_description(message: Message, state: FSMContext):
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Создание отменено.", reply_markup=main_menu_kb())
        return

    description = "" if message.text == "⏭ Пропустить" else message.text.strip()[:500]
    await state.update_data(description=description)
    await message.answer(
        "Шаг 3/6 — Что у тебя есть из выпивки?\n"
        "Например: «Бутылка виски Jameson, 2 банки пива»",
        reply_markup=cancel_kb()
    )
    await state.set_state(CreateListing.waiting_drinks)


@router.message(CreateListing.waiting_drinks)
async def process_drinks(message: Message, state: FSMContext):
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Создание отменено.", reply_markup=main_menu_kb())
        return

    drinks = message.text.strip()[:200]
    await state.update_data(drinks=drinks)
    await message.answer(
        "Шаг 4/6 — Есть что-нибудь поесть? (закуска, снеки)\n"
        "Например: «Чипсы, орешки» или нажми «Пропустить»",
        reply_markup=skip_kb()
    )
    await state.set_state(CreateListing.waiting_snacks)


@router.message(CreateListing.waiting_snacks)
async def process_snacks(message: Message, state: FSMContext):
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Создание отменено.", reply_markup=main_menu_kb())
        return

    snacks = "" if message.text == "⏭ Пропустить" else message.text.strip()[:200]
    await state.update_data(snacks=snacks)
    await message.answer(
        "Шаг 5/6 — Отправь свою геолокацию.\n"
        "Это нужно, чтобы люди рядом могли найти тебя.\n\n"
        "📍 Нажми кнопку ниже или отправь геолокацию вручную.",
        reply_markup=location_kb()
    )
    await state.set_state(CreateListing.waiting_location)


@router.message(CreateListing.waiting_location, F.location)
async def process_location(message: Message, state: FSMContext):
    lat = message.location.latitude
    lon = message.location.longitude
    await state.update_data(latitude=lat, longitude=lon, location_name="")
    await message.answer(
        "Шаг 6/6 — Сколько человек ты готов принять? (введи число от 1 до 10)",
        reply_markup=cancel_kb()
    )
    await state.set_state(CreateListing.waiting_max_people)


@router.message(CreateListing.waiting_location)
async def process_location_text(message: Message, state: FSMContext):
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Создание отменено.", reply_markup=main_menu_kb())
        return
    await message.answer(
        "Пожалуйста, отправь геолокацию через кнопку 📍 или нажми «Отмена».",
        reply_markup=location_kb()
    )


@router.message(CreateListing.waiting_max_people)
async def process_max_people(message: Message, state: FSMContext):
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Создание отменено.", reply_markup=main_menu_kb())
        return

    try:
        max_p = int(message.text.strip())
        if max_p < 1 or max_p > 10:
            raise ValueError
    except ValueError:
        await message.answer("Введи число от 1 до 10.")
        return

    await state.update_data(max_people=max_p)
    data = await state.get_data()

    preview = (
        f"📋 *Предпросмотр объявления:*\n\n"
        f"*{data['title']}*\n"
    )
    if data.get("description"):
        preview += f"💬 {data['description']}\n"
    preview += (
        f"🍾 Выпивка: {data['drinks']}\n"
        f"🍕 Закуска: {data.get('snacks') or 'не указано'}\n"
        f"👥 Мест: {max_p}\n"
        f"⏳ Объявление будет активно 6 часов\n\n"
        f"Опубликовать?"
    )
    await message.answer(preview, parse_mode="Markdown", reply_markup=confirm_kb())
    await state.set_state(CreateListing.waiting_confirm)


@router.callback_query(F.data == "listing_confirm", CreateListing.waiting_confirm)
async def confirm_listing(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    listing_id = await create_listing(
        user_id=callback.from_user.id,
        title=data["title"],
        description=data.get("description", ""),
        drinks=data["drinks"],
        snacks=data.get("snacks", ""),
        latitude=data["latitude"],
        longitude=data["longitude"],
        location_name=data.get("location_name", ""),
        max_people=data.get("max_people", 1)
    )

    await callback.message.edit_text(
        f"✅ Объявление *#{listing_id}* опубликовано!\n\n"
        f"Люди рядом смогут найти тебя в течение 6 часов.\n"
        f"Как только кто-то откликнется — ты получишь уведомление.",
        parse_mode="Markdown"
    )
    await callback.message.answer("Главное меню:", reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "listing_cancel")
async def cancel_listing(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Создание объявления отменено.")
    await callback.message.answer("Главное меню:", reply_markup=main_menu_kb())
    await callback.answer()


# ─── МОИ ОБЪЯВЛЕНИЯ ───────────────────────────────────────────────────────────

@router.message(F.text == "📋 Мои объявления")
@router.message(Command("mylistings"))
async def cmd_my_listings(message: Message, state: FSMContext):
    await state.clear()
    listings = await get_user_listings(message.from_user.id)

    if not listings:
        await message.answer(
            "У тебя пока нет объявлений.\n"
            "Нажми «📢 Создать объявление», чтобы начать!",
            reply_markup=main_menu_kb()
        )
        return

    await message.answer(
        f"📋 *Твои объявления* ({len(listings)} шт.):",
        parse_mode="Markdown",
        reply_markup=main_menu_kb()
    )

    for listing in listings:
        text = format_listing(listing)
        kb = listing_actions_kb(listing["id"], is_owner=True) if listing["status"] == "active" else None
        await message.answer(text, parse_mode="Markdown", reply_markup=kb)


@router.callback_query(F.data.startswith("listing_close:"))
async def close_listing_cb(callback: CallbackQuery):
    listing_id = int(callback.data.split(":")[1])
    listing = await get_listing(listing_id)

    if not listing or listing["user_id"] != callback.from_user.id:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    await close_listing(listing_id)
    await callback.message.edit_text(
        callback.message.text + "\n\n🔴 *Объявление закрыто.*",
        parse_mode="Markdown"
    )
    await callback.answer("Объявление закрыто.")


# ─── ПОИСК ОБЪЯВЛЕНИЙ ─────────────────────────────────────────────────────────

@router.message(F.text == "🔍 Найти собутыльника")
@router.message(Command("find"))
async def cmd_find(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🔍 *Поиск собутыльника*\n\n"
        "Отправь свою геолокацию, и я покажу объявления в радиусе 5 км.",
        parse_mode="Markdown",
        reply_markup=location_kb()
    )


@router.message(F.location)
async def handle_find_location(message: Message, state: FSMContext):
    current_state = await state.get_state()

    # Если идёт создание объявления — не перехватываем
    if current_state == CreateListing.waiting_location.state:
        return

    lat = message.location.latitude
    lon = message.location.longitude

    await message.answer("🔍 Ищу объявления рядом...", reply_markup=main_menu_kb())

    all_listings = await get_active_listings_near(lat, lon)
    # Исключаем свои объявления
    all_listings = [l for l in all_listings if l["user_id"] != message.from_user.id]
    nearby = filter_by_radius(all_listings, lat, lon, radius_km=5.0)

    if not nearby:
        await message.answer(
            "😔 Пока никого нет рядом в радиусе 5 км.\n\n"
            "Может, создашь своё объявление и подождёшь? 🍺",
            reply_markup=main_menu_kb()
        )
        return

    # Сохраняем список для навигации
    await state.update_data(browse_listings=nearby, browse_idx=0)

    text = format_listing(nearby[0], show_distance=True)
    await message.answer(
        f"🎉 Найдено *{len(nearby)}* объявлений рядом!\n\n{text}",
        parse_mode="Markdown",
        reply_markup=listings_nav_kb(nearby, 0)
    )


@router.callback_query(F.data.startswith("browse:"))
async def browse_listings(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    listings = data.get("browse_listings", [])

    if not listings or idx >= len(listings):
        await callback.answer("Список устарел. Поищи снова.", show_alert=True)
        return

    await state.update_data(browse_idx=idx)
    text = format_listing(listings[idx], show_distance=True)
    await callback.message.edit_text(
        f"🎉 Найдено *{len(listings)}* объявлений рядом!\n\n{text}",
        parse_mode="Markdown",
        reply_markup=listings_nav_kb(listings, idx)
    )
    await callback.answer()


@router.callback_query(F.data == "browse_noop")
async def browse_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "browse_close")
async def browse_close(callback: CallbackQuery, state: FSMContext):
    await state.update_data(browse_listings=[], browse_idx=0)
    await callback.message.edit_text("Поиск закрыт.")
    await callback.answer()
