from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from database.db import (
    get_user, create_listing, get_user_active_listing, 
    close_listing, get_next_listing_for_user, add_like
)
from states.states import CreateListing, BrowseAnketas
from utils.keyboards import (
    main_menu_kb, location_kb, cancel_kb, skip_kb, 
    confirm_kb, swipe_kb, my_listing_actions_kb
)
from utils.helpers import calculate_distance

router = Router()

# ─── СОЗДАНИЕ АНКЕТЫ ──────────────────────────────────────────────────────────

@router.message(F.text == "📢 Создать анкету")
async def cmd_create_listing(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала нажми /start для регистрации.")
        return

    active = await get_user_active_listing(message.from_user.id)
    if active:
        await message.answer("У тебя уже есть активная анкета! Удали её, чтобы создать новую.")
        return

    await state.clear()
    await message.answer(
        "📸 *Шаг 1/6: Пришли фото.*\n\n"
        "Это может быть твой накрытый стол, напитки или просто селфи.",
        parse_mode="Markdown",
        reply_markup=cancel_kb()
    )
    await state.set_state(CreateListing.waiting_photo)

@router.message(CreateListing.waiting_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await message.answer(
        "✍️ *Шаг 2/6: Заголовок анкеты.*\n\n"
        "Например: «Виски и пицца» или «Ищу компанию на вечер»",
        parse_mode="Markdown"
    )
    await state.set_state(CreateListing.waiting_title)

@router.message(CreateListing.waiting_title)
async def process_title(message: Message, state: FSMContext):
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_kb())
        return
    await state.update_data(title=message.text[:100])
    await message.answer("📝 *Шаг 3/6: Описание.*\n\nРасскажи подробнее, где ты и какая компания нужна.", parse_mode="Markdown", reply_markup=skip_kb())
    await state.set_state(CreateListing.waiting_description)

@router.message(CreateListing.waiting_description)
async def process_description(message: Message, state: FSMContext):
    desc = "" if message.text == "⏭ Пропустить" else message.text
    await state.update_data(description=desc)
    await message.answer("🍾 *Шаг 4/6: Что из выпивки?*", parse_mode="Markdown", reply_markup=cancel_kb())
    await state.set_state(CreateListing.waiting_drinks)

@router.message(CreateListing.waiting_drinks)
async def process_drinks(message: Message, state: FSMContext):
    await state.update_data(drinks=message.text)
    await message.answer("📍 *Шаг 5/6: Твоя локация.*\n\nНажми кнопку ниже, чтобы люди рядом могли тебя найти.", parse_mode="Markdown", reply_markup=location_kb())
    await state.set_state(CreateListing.waiting_location)

@router.message(CreateListing.waiting_location, F.location)
async def process_location(message: Message, state: FSMContext):
    await state.update_data(lat=message.location.latitude, lon=message.location.longitude)
    await message.answer("👥 *Шаг 6/6: Сколько человек ищешь?* (введи число)", parse_mode="Markdown", reply_markup=cancel_kb())
    await state.set_state(CreateListing.waiting_max_people)

@router.message(CreateListing.waiting_max_people)
async def process_max_people(message: Message, state: FSMContext):
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_kb())
        return

    try:
        count = int(message.text.strip())
    except ValueError:
        await message.answer("Пожалуйста, введи только число (например: 2).")
        return

    await state.update_data(max_people=count)
    data = await state.get_data()
    
    try:
        await message.answer_photo(
            photo=data['photo_id'],
            caption=(
                f"📋 *Предпросмотр вашей анкеты:*\n\n"
                f"📌 *{data['title']}*\n"
                f"📝 {data['description']}\n\n"
                f"🍾 *Выпивка:* {data['drinks']}\n"
                f"👥 *Мест:* {count}\n\n"
                f"Всё верно? Нажми «Опубликовать», чтобы анкету увидели другие."
            ),
            parse_mode="Markdown",
            reply_markup=confirm_kb()
        )
        await state.set_state(CreateListing.waiting_confirm)
    except Exception as e:
        # Если фото не отправляется, пробуем текстом
        await message.answer(
            f"📋 *Предпросмотр (без фото):*\n\n"
            f"📌 *{data['title']}*\n"
            f"📝 {data['description']}\n\n"
            f"🍾 *Выпивка:* {data['drinks']}\n"
            f"👥 *Мест:* {count}",
            parse_mode="Markdown",
            reply_markup=confirm_kb()
        )
        await state.set_state(CreateListing.waiting_confirm)

@router.callback_query(F.data == "listing_confirm", CreateListing.waiting_confirm)
async def confirm_listing_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await create_listing(
        user_id=callback.from_user.id,
        title=data['title'],
        description=data['description'],
        drinks=data['drinks'],
        snacks="",
        photo_id=data['photo_id'],
        latitude=data['lat'],
        longitude=data['lon'],
        location_name="",
        max_people=data['max_people']
    )
    await state.clear()
    await callback.message.answer("✅ Анкета опубликована! Теперь тебя видят другие.", reply_markup=main_menu_kb())
    await callback.answer()

# ─── ПРОСМОТР АНКЕТ (СВАЙПЫ) ──────────────────────────────────────────────────

@router.message(F.text == "🔍 Искать компанию")
async def cmd_browse(message: Message, state: FSMContext):
    await message.answer("📍 Для поиска нужно отправить свою геолокацию.", reply_markup=location_kb())

@router.message(F.location)
async def handle_location_for_browse(message: Message, state: FSMContext):
    # Если мы в процессе создания анкеты — игнорируем здесь
    if await state.get_state() == CreateListing.waiting_location:
        return
        
    lat, lon = message.location.latitude, message.location.longitude
    await state.update_data(user_lat=lat, user_lon=lon)
    await show_next_anketa(message, state)

async def show_next_anketa(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.chat.id
    
    anketa = await get_next_listing_for_user(user_id, data.get('user_lat'), data.get('user_lon'))
    
    if not anketa:
        await message.answer("😔 Анкеты закончились! Попробуй позже или расширь поиск.", reply_markup=main_menu_kb())
        await state.clear()
        return

    dist = calculate_distance(data.get('user_lat'), data.get('user_lon'), anketa['latitude'], anketa['longitude'])
    
    text = (
        f"*{anketa['title']}*\n"
        f"{anketa['description']}\n\n"
        f"🍾 {anketa['drinks']}\n"
        f"📍 Расстояние: {dist:.1f} км\n"
        f"⭐ Рейтинг: {anketa['rating']} ({anketa['reviews_count']} отз.)"
    )
    
    if isinstance(message, CallbackQuery):
        await message.message.answer_photo(photo=anketa['photo_id'], caption=text, parse_mode="Markdown", reply_markup=swipe_kb(anketa['id']))
        await message.message.delete()
    else:
        await message.answer_photo(photo=anketa['photo_id'], caption=text, parse_mode="Markdown", reply_markup=swipe_kb(anketa['id']))

@router.callback_query(F.data == "swipe:close")
async def close_swipe(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Просмотр завершен.", reply_markup=main_menu_kb())
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("swipe:"))
async def handle_swipe(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return
        
    action = parts[1]
    listing_id = int(parts[2])
    
    # Получаем информацию об анкете, чтобы знать владельца
    from database.db import get_listing
    anketa = await get_listing(listing_id)
    
    if not anketa:
        await callback.answer("Анкета больше не активна.")
        await show_next_anketa(callback, state)
        return

    is_like = 1 if action == "like" else 0
    is_match = await add_like(callback.from_user.id, anketa['user_id'], listing_id, is_like)
    
    if is_match:
        await callback.message.answer(
            f"🎉 *Взаимная симпатия!*\n\n"
            f"Владелец анкеты: *{anketa['first_name']}*\n"
            f"Можешь написать ему: @{anketa['username'] or 'id' + str(anketa['user_id'])}", 
            parse_mode="Markdown"
        )
        # Уведомляем владельца
        try:
            await callback.bot.send_message(
                anketa['user_id'], 
                f"❤️ *У тебя взаимная симпатия!*\n\n"
                f"Пользователь {callback.from_user.first_name} лайкнул тебя в ответ.\n"
                f"Связь: @{callback.from_user.username or 'id' + str(callback.from_user.id)}",
                parse_mode="Markdown"
            )
        except:
            pass
    elif is_like:
        try:
            await callback.bot.send_message(
                anketa['user_id'], 
                f"❤️ Кто-то лайкнул твою анкету! Зайди в поиск, чтобы найти взаимность."
            )
        except:
            pass

    await show_next_anketa(callback, state)
    await callback.answer()

# ─── МОЯ АНКЕТА ───────────────────────────────────────────────────────────────

@router.message(F.text == "📋 Моя анкета")
async def cmd_my_anketa(message: Message):
    anketa = await get_user_active_listing(message.from_user.id)
    if not anketa:
        await message.answer("У тебя нет активной анкеты.", reply_markup=main_menu_kb())
        return
    
    text = (
        f"📋 *Твоя активная анкета:*\n\n"
        f"*{anketa['title']}*\n"
        f"{anketa['description']}\n\n"
        f"🍾 {anketa['drinks']}\n"
        f"👥 Мест: {anketa['max_people']}"
    )
    await message.answer_photo(photo=anketa['photo_id'], caption=text, parse_mode="Markdown", reply_markup=my_listing_actions_kb(anketa['id']))

@router.callback_query(F.data.startswith("listing_close:"))
async def handle_close_listing(callback: CallbackQuery):
    listing_id = int(callback.data.split(":")[1])
    await close_listing(listing_id)
    await callback.message.answer("🔴 Анкета удалена.")
    await callback.message.delete()
    await callback.answer()
