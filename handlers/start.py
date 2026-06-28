from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from database.db import get_user, create_user, update_user_profile, get_user_reviews
from states.states import ProfileSetup, FeedbackStates
from utils.keyboards import main_menu_kb, cancel_kb, skip_kb

router = Router()

WELCOME_TEXT = """
🍺 *Добро пожаловать в Собутыльник!*

Это сервис для поиска компании, чтобы скоротать вечер вместе.

Как это работает:
1️⃣ Замути движ — загрузи фото, укажи что есть выпить
2️⃣ Ищи вписку — листай анкеты других людей рядом
3️⃣ Ставь лайки ❤️ и получай взаимность
4️⃣ Встречайтесь и оставляйте отзывы

⚠️ *Важно:* Сервис только для совершеннолетних (18+). Пей ответственно!
"""

def get_stars_local(rating: float) -> str:
    full = int(round(rating or 0))
    return "⭐" * full + "☆" * (5 - full)

def format_profile_html(user: dict) -> str:
    name = user.get("first_name", "Аноним").replace("<", "&lt;").replace(">", "&gt;")
    username = f"@{user['username']}" if user.get("username") else "id" + str(user['id'])
    age = f"{user['age']} лет" if user.get("age") else "не указан"
    bio = (user.get("bio") or "не заполнено").replace("<", "&lt;").replace(">", "&gt;")
    rating = user.get("rating", 0.0)
    reviews_count = user.get("reviews_count", 0)

    return (
        f"👤 <b>{name}</b> ({username})\n"
        f"🎂 Возраст: {age}\n"
        f"📝 О себе: <i>{bio}</i>\n"
        f"⭐ Рейтинг: {get_stars_local(rating)} ({rating:.1f} / {reviews_count} отзывов)"
    )

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = await get_user(message.from_user.id)

    if not user:
        await create_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name
        )
        await message.answer(
            WELCOME_TEXT,
            parse_mode="Markdown"
        )
        await message.answer(
            "Для начала давай немного познакомимся.\n\n"
            "Сколько тебе лет? (введи число или нажми «Пропустить»)",
            reply_markup=skip_kb()
        )
        await state.set_state(ProfileSetup.waiting_age)
    else:
        await message.answer(
            f"С возвращением, *{message.from_user.first_name}*! 🍻",
            parse_mode="Markdown",
            reply_markup=main_menu_kb()
        )

@router.message(ProfileSetup.waiting_age)
async def process_age(message: Message, state: FSMContext):
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Настройка профиля отменена.", reply_markup=main_menu_kb())
        return

    age = None
    if message.text != "⏭ Пропустить":
        try:
            age = int(message.text.strip())
            if age < 18 or age > 100:
                await message.answer("⚠️ Пожалуйста, укажи реальный возраст (18–100 лет).")
                return
        except ValueError:
            await message.answer("Введи число или нажми «Пропустить».")
            return

    await state.update_data(age=age)
    await message.answer(
        "Расскажи немного о себе — это увидят другие пользователи.\n"
        "Например: «Люблю виски и хорошие разговоры» (или нажми «Пропустить»)",
        reply_markup=skip_kb()
    )
    await state.set_state(ProfileSetup.waiting_bio)

@router.message(ProfileSetup.waiting_bio)
async def process_bio(message: Message, state: FSMContext):
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Настройка профиля отменена.", reply_markup=main_menu_kb())
        return

    bio = None
    if message.text != "⏭ Пропустить":
        bio = message.text.strip()[:300]

    data = await state.get_data()
    age = data.get("age")

    await update_user_profile(message.from_user.id, age, bio)
    await state.clear()
    await message.answer(
        "✅ Профиль сохранён! Теперь можешь замутить движ или искать вписку.",
        reply_markup=main_menu_kb()
    )

@router.message(F.text == "😎 Мой профиль")
@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext):
    try:
        await state.clear()
        from database.db import get_user, create_user, get_user_active_listing, get_user_reviews
        from utils.keyboards import my_listing_actions_kb, main_menu_kb
        
        user_id = message.from_user.id
        user = await get_user(user_id)
        
        if not user:
            await create_user(user_id, message.from_user.username, message.from_user.first_name)
            user = await get_user(user_id)

        profile_text = format_profile_html(user)
        reviews = await get_user_reviews(user_id)

        if reviews:
            profile_text += "\n\n<b>Последние отзывы (взаимные):</b>\n"
            for r in reviews[:3]:
                author = r.get("author_name", "Аноним").replace("<", "&lt;").replace(">", "&gt;")
                profile_text += f"\n{get_stars_local(r['rating'])} от <b>{author}</b>\n<i>{r.get('text', '') or 'без текста'}</i>\n"

        anketa = await get_user_active_listing(user_id)
        if anketa and anketa.get('photo_id'):
            anketa_text = (
                f"\n🔥 <b>Твой активный движ:</b>\n"
                f"📌 <b>{anketa['title']}</b>\n"
                f"⏳ Активен до: {anketa['expires_at']}\n"
            )
            try:
                await message.answer_photo(
                    photo=anketa['photo_id'], 
                    caption=profile_text + "\n" + anketa_text, 
                    parse_mode="HTML", 
                    reply_markup=my_listing_actions_kb(anketa['id'])
                )
                return
            except: pass
        
        await message.answer(profile_text, parse_mode="HTML", reply_markup=main_menu_kb())
        
    except Exception as e:
        import logging
        logging.error(f"FATAL ERROR in cmd_profile: {e}")
        await message.answer("⚠️ Ошибка профиля. Попробуй /start")

@router.message(F.text == "📜 Репутация")
async def cmd_my_reviews(message: Message):
    reviews = await get_user_reviews(message.from_user.id)
    if not reviews:
        await message.answer("У тебя пока нет отзывов.")
        return
    
    text = "📜 *Твоя репутация:*\n"
    for r in reviews:
        author = r.get("author_name", "Аноним")
        text += f"\n{get_stars(r['rating'])} от *{author}*\n_{r.get('text', '') or 'без текста'}_\n"
    
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "📩 Написать админу")
async def cmd_feedback(message: Message, state: FSMContext):
    await message.answer(
        "📝 *Обратная связь*\n\n"
        "Напиши своё сообщение администратору. Это может быть баг, предложение или жалоба.\n\n"
        "Я перешлю его разработчикам!",
        parse_mode="Markdown",
        reply_markup=cancel_kb()
    )
    await state.set_state(FeedbackStates.waiting_feedback)

@router.message(FeedbackStates.waiting_feedback)
async def process_feedback(message: Message, state: FSMContext):
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_kb())
        return

    feedback_text = message.text.strip()
    from handlers.admin import ADMIN_IDS
    
    user_name = message.from_user.first_name.replace("<", "&lt;").replace(">", "&gt;")
    user_link = f"@{message.from_user.username}" if message.from_user.username else f'<a href="tg://user?id={message.from_user.id}">{user_name}</a>'
    
    admin_msg = (
        f"📩 <b>НОВОЕ СООБЩЕНИЕ АДМИНУ</b>\n\n"
        f"👤 От: {user_link} (ID: <code>{message.from_user.id}</code>)\n\n"
        f"💬 Текст:\n{feedback_text}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, admin_msg, parse_mode="HTML")
        except: pass

    await state.clear()
    await message.answer(
        "✅ Твоё сообщение отправлено администратору! Спасибо за обратную связь.",
        reply_markup=main_menu_kb()
    )
