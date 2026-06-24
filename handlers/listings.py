from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from database.db import (
    create_listing, get_user_active_listing, 
    get_next_listing_for_user, add_like, get_listing, close_listing
)
from states.states import CreateListing
from utils.keyboards import (
    main_menu_kb, cancel_kb, location_kb, 
    confirm_kb, swipe_kb, my_listing_actions_kb
)
from utils.helpers import get_distance_text

router = Router()

# ─── СОЗДАНИЕ АНКЕТЫ (ЗАМУТИТЬ ДВИЖ) ──────────────────────────────────────────

@router.message(F.text == "🍻 Замутить движ")
async def cmd_create_listing(message: Message, state: FSMContext):
    active = await get_user_active_listing(message.from_user.id)
    if active:
        await message.answer(
            "У тебя уже есть активный движ! Сначала удали старый в профиле.",
            reply_markup=main_menu_kb()
        )
        return

    await state.set_state(CreateListing.waiting_title)
    await message.answer(
        "Придумай крутой заголовок для твоего движа!\nНапример: «Виски-пати на районе» или «Пиво и плойка»",
        reply_markup=cancel_kb()
    )

@router.message(CreateListing.waiting_title)
async def process_title(message: Message, state: FSMContext):
    if not message.text: return
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_kb())
        return
    
    await state.update_data(title=message.text.strip()[:50])
    await state.set_state(CreateListing.waiting_description)
    await message.answer("Теперь добавь описание — что планируете делать?", reply_markup=cancel_kb())

@router.message(CreateListing.waiting_description)
async def process_description(message: Message, state: FSMContext):
    if not message.text: return
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_kb())
        return
    
    await state.update_data(description=message.text.strip()[:300])
    await state.set_state(CreateListing.waiting_drinks)
    await message.answer("Что по напиткам? (например: Jameson, светлое нефильтрованное)", reply_markup=cancel_kb())

@router.message(CreateListing.waiting_drinks)
async def process_drinks(message: Message, state: FSMContext):
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_kb())
        return
    await state.update_data(drinks=message.text.strip()[:100])
    await state.set_state(CreateListing.waiting_photo)
    await message.answer("Скинь фотку твоего стола или компании! 📸")

@router.message(CreateListing.waiting_photo)
async def process_photo(message: Message, state: FSMContext):
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_kb())
        return

    if not message.photo:
        await message.answer("Пожалуйста, пришли именно фото! 📸")
        return

    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await state.set_state(CreateListing.waiting_location)
    await message.answer("Фото принято! ✅\n\nТеперь скинь свою геолокацию, чтобы тебя нашли те, кто рядом.", reply_markup=location_kb())

@router.message(CreateListing.waiting_location, F.location)
async def process_location(message: Message, state: FSMContext):
    lat = message.location.latitude
    lon = message.location.longitude
    await state.update_data(lat=lat, lon=lon)
    await state.set_state(CreateListing.waiting_max_people)
    await message.answer("Сколько человек готов принять? (введи число)", reply_markup=cancel_kb())

@router.message(CreateListing.waiting_max_people)
async def process_max_people(message: Message, state: FSMContext):
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_kb())
        return

    try:
        count = int(message.text.strip())
    except ValueError:
        await message.answer("Пожалуйста, введи только число.")
        return

    await state.update_data(max_people=count)
    data = await state.get_data()
    
    preview_text = (
        f"📋 *Твой будущий движ:*\n\n"
        f"📌 *{data['title']}*\n"
        f"📝 {data['description']}\n\n"
        f"🍾 *Напитки:* {data['drinks']}\n"
        f"👥 *Мест:* {count}\n\n"
        f"Всё чётко? Публикуем?"
    )
    
    try:
        await message.answer_photo(
            photo=data['photo_id'],
            caption=preview_text,
            parse_mode="Markdown",
            reply_markup=confirm_kb()
        )
    except:
        await message.answer(preview_text, parse_mode="Markdown", reply_markup=confirm_kb())
    
    await state.set_state(CreateListing.waiting_confirm)

@router.callback_query(F.data == "listing_confirm", CreateListing.waiting_confirm)
async def confirm_listing_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    # Сохраняем анкету
    await create_listing(
        user_id=callback.from_user.id,
        title=data['title'],
        description=data['description'],
        drinks=data['drinks'],
        snacks="",
        photo_id=data['photo_id'],
        latitude=data['lat'],
        longitude=data['lon'],
        location_name="Рядом",
        max_people=data['max_people']
    )
    # Очищаем состояние СРАЗУ ПОСЛЕ сохранения
    await state.clear()
    
    # Отправляем подтверждение с НОВОЙ клавиатурой (main_menu_kb)
    await callback.message.answer(
        "🚀 *Движ опубликован!*\n\n"
        "Теперь другие пользователи увидят твою анкету в поиске. "
        "Как только кто-то лайкнет тебя — я пришлю уведомление!",
        parse_mode="Markdown",
        reply_markup=main_menu_kb()
    )
    
    # Удаляем сообщение с предпросмотром, чтобы не висели старые кнопки
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer("Опубликовано!")

@router.callback_query(F.data == "listing_cancel", CreateListing.waiting_confirm)
async def cancel_listing_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Отменено.", reply_markup=main_menu_kb())
    await callback.message.delete()
    await callback.answer()

# ─── ПОИСК АНКЕТ (НАЙТИ ВПИСКУ) ────────────────────────────────────────────────

@router.message(F.text == "🕵️ Найти вписку")
async def cmd_search(message: Message, state: FSMContext):
    await message.answer("Где ищем? Скинь свою локацию.", reply_markup=location_kb())
    await state.set_state(CreateListing.waiting_search_location)

@router.message(CreateListing.waiting_search_location, F.location)
async def process_search_location(message: Message, state: FSMContext):
    await state.update_data(search_lat=message.location.latitude, search_lon=message.location.longitude)
    await show_next_anketa(message, state)

async def show_next_anketa(message, state: FSMContext):
    data = await state.get_data()
    lat = data.get('search_lat')
    lon = data.get('search_lon')
    
    if not lat: # Если начали поиск без локации
        await message.answer("Сначала скинь локацию!", reply_markup=location_kb())
        return

    anketa = await get_next_listing_for_user(message.from_user.id, lat, lon)
    
    if not anketa:
        text = "😢 Больше движух рядом нет. Попробуй позже или замути свой!"
        if isinstance(message, CallbackQuery):
            await message.message.answer(text, reply_markup=main_menu_kb())
            await message.message.delete()
        else:
            await message.answer(text, reply_markup=main_menu_kb())
        return

    from utils.helpers import calculate_distance
    d = calculate_distance(lat, lon, anketa['latitude'], anketa['longitude'])
    dist = get_distance_text(d)
    text = (
        f"🔥 *{anketa['title']}*\n\n"
        f"{anketa['description']}\n\n"
        f"🍾 {anketa['drinks']}\n"
        f"👥 Мест: {anketa['max_people']}\n"
        f"📍 {dist} от тебя\n"
        f"👤 {anketa['first_name']} (⭐ {anketa['rating']:.1f})"
    )

    if isinstance(message, CallbackQuery):
        # Удаляем старую и шлем новую
        await message.message.delete()
        await message.message.answer_photo(
            photo=anketa['photo_id'], 
            caption=text, 
            parse_mode="Markdown", 
            reply_markup=swipe_kb(anketa['id'])
        )
    else:
        await message.answer_photo(
            photo=anketa['photo_id'], 
            caption=text, 
            parse_mode="Markdown", 
            reply_markup=swipe_kb(anketa['id'])
        )

@router.callback_query(F.data == "swipe:close")
async def close_swipe(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Поиск завершен.", reply_markup=main_menu_kb())
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("swipe:"))
async def handle_swipe(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    action = parts[1]
    listing_id = int(parts[2])
    
    anketa = await get_listing(listing_id)
    if not anketa:
        await callback.answer("Этот движ уже закончился.")
        await show_next_anketa(callback, state)
        return

    is_like = 1 if action == "like" else 0
    
    # Сначала отвечаем на колбэк, чтобы кнопка не "висела"
    await callback.answer("Принято!" if is_like else "Пропущено")
    
    # Записываем лайк/дизлайк и проверяем матч
    is_match = await add_like(callback.from_user.id, anketa['user_id'], listing_id, is_like)
    
    if is_match and is_like:
        # Ссылки на пользователей
        host_link = f"@{anketa['username']}" if anketa['username'] else f"[{anketa['first_name']}](tg://user?id={anketa['user_id']})"
        guest_link = f"@{callback.from_user.username}" if callback.from_user.username else f"[{callback.from_user.first_name}](tg://user?id={callback.from_user.id})"
        
        # Уведомление тому, кто нажал лайк СЕЙЧАС
        await callback.message.answer(
            f"🎉 *ЕСТЬ КОНТАКТ!*\n\n"
            f"Тебе понравился движ *{anketa['title']}*, а ты понравился им!\n"
            f"Связь с организатором: {host_link}", 
            parse_mode="Markdown"
        )
        
        # Уведомление второму участнику (организатору)
        try:
            await callback.bot.send_message(
                anketa['user_id'], 
                f"🎉 *ВЗАИМНЫЙ ЛАЙК!*\n\n"
                f"Пользователь {callback.from_user.first_name} лайкнул твой движ *{anketa['title']}*.\n"
                f"Вы понравились друг другу! \n"
                f"Связь: {guest_link}",
                parse_mode="Markdown"
            )
        except: pass
    elif is_like:
        # Просто уведомление о лайке (без контактов)
        try:
            await callback.bot.send_message(
                anketa['user_id'], 
                f"❤️ Кто-то лайкнул твой движ! Зайди в поиск, чтобы найти взаимность."
            )
        except: pass

    # Показываем следующую анкету
    await show_next_anketa(callback, state)

@router.callback_query(F.data.startswith("report:"))
async def handle_report(callback: CallbackQuery):
    listing_id = int(callback.data.split(":")[1])
    anketa = await get_listing(listing_id)
    
    if anketa:
        from handlers.admin import ADMIN_IDS
        for admin_id in ADMIN_IDS:
            try:
                await callback.bot.send_message(
                    admin_id,
                    f"🚩 *ЖАЛОБА на анкету!*\n\n"
                    f"От кого: {callback.from_user.first_name} (ID: `{callback.from_user.id}`)\n"
                    f"На кого: {anketa['first_name']} (ID: `{anketa['user_id']}`)\n"
                    f"Анкета ID: `{listing_id}`\n"
                    f"Заголовок: {anketa['title']}",
                    parse_mode="Markdown"
                )
            except: pass
    
    await callback.answer("Жалоба отправлена админу. Спасибо!", show_alert=True)
    await show_next_anketa(callback, None)

# ─── МОЙ ПРОФИЛЬ (АНКЕТА) ─────────────────────────────────────────────────────

@router.message(F.text == "😎 Мой профиль")
async def cmd_my_anketa(message: Message, state: FSMContext):
    # Сбрасываем любые зависшие состояния при переходе в профиль
    await state.clear()
    
    anketa = await get_user_active_listing(message.from_user.id)
    if not anketa:
        # Если анкеты нет, пробуем показать просто профиль пользователя из start.py
        from handlers.start import cmd_profile
        await cmd_profile(message, state)
        return
    
    # Добавим информацию о времени истечения
    expires_at = anketa.get('expires_at', 'неизвестно')
    
    text = (
        f"😎 *Твой активный движ:*\n\n"
        f"📌 *{anketa['title']}*\n"
        f"📝 {anketa['description']}\n\n"
        f"🍾 Напитки: {anketa['drinks']}\n"
        f"👥 Мест: {anketa['max_people']}\n"
        f"📅 Создан: {anketa['created_at']}\n"
        f"⏳ Активен до: {expires_at}"
    )
    
    try:
        await message.answer_photo(
            photo=anketa['photo_id'], 
            caption=text, 
            parse_mode="Markdown", 
            reply_markup=my_listing_actions_kb(anketa['id'])
        )
    except Exception as e:
        await message.answer(text, parse_mode="Markdown", reply_markup=my_listing_actions_kb(anketa['id']))

@router.callback_query(F.data.startswith("listing_close:"))
async def handle_close_listing(callback: CallbackQuery):
    listing_id = int(callback.data.split(":")[1])
    await close_listing(listing_id)
    await callback.message.answer("Твой движ удален. Можешь замутить новый! 🍻", reply_markup=main_menu_kb())
    await callback.message.delete()
    await callback.answer()
