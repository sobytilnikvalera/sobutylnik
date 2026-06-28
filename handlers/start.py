from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from database.db import get_user, create_user, update_user_profile, get_user_reviews
from states.states import ProfileSetup
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

def get_stars(rating: float) -> str:
    full = int(round(rating))
    return "⭐" * full + "☆" * (5 - full)

def format_profile(user: dict) -> str:
    name = user.get("first_name", "Аноним")
    username = f"@{user['username']}" if user.get("username") else "id" + str(user['id'])
    age = f"{user['age']} лет" if user.get("age") else "не указан"
    bio = user.get("bio") or "не заполнено"
    rating = user.get("rating", 0.0)
    reviews_count = user.get("reviews_count", 0)

    return (
        f"👤 *{name}* ({username})\n"
        f"🎂 Возраст: {age}\n"
        f"📝 О себе: {bio}\n"
        f"⭐ Рейтинг: {get_stars(rating)} ({rating:.1f} / {reviews_count} отзывов)"
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
        user = await get_user(message.from_user.id)
        
        # Если пользователя нет в БД, создаем его (на всякий случай)
        if not user:
            from database.db import create_user
            await create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
            user = await get_user(message.from_user.id)

        from database.db import get_user_active_listing
        from utils.keyboards import my_listing_actions_kb
        
        anketa = await get_user_active_listing(message.from_user.id)
        
        profile_text = format_profile(user)
        reviews = await get_user_reviews(message.from_user.id)

        if reviews:
            profile_text += "\n\n*Последние отзывы (видны только взаимные):*\n"
            for r in reviews[:3]:
                author = r.get("author_name", "Аноним")
                profile_text += f"\n{get_stars(r['rating'])} от *{author}*\n_{r.get('text', '') or 'без текста'}_\n"

        # Если есть активная анкета, показываем её
        if anketa and anketa.get('photo_id'):
            anketa_text = (
                f"\n🔥 *Твой активный движ:*\n"
                f"📌 *{anketa['title']}*\n"
                f"⏳ Активен до: {anketa['expires_at']}\n"
            )
            full_text = profile_text + "\n" + anketa_text
            
            try:
                await message.answer_photo(
                    photo=anketa['photo_id'], 
                    caption=full_text, 
                    parse_mode="Markdown", 
                    reply_markup=my_listing_actions_kb(anketa['id'])
                )
                return
            except Exception as e:
                logging.error(f"Photo send failed: {e}")
        
        # Если фото нет или не отправилось, шлем просто текст
        await message.answer(profile_text, parse_mode="Markdown", reply_markup=main_menu_kb())
        
    except Exception as e:
        import logging
        logging.error(f"CRITICAL ERROR in cmd_profile: {e}")
        await message.answer("⚠️ Ошибка при загрузке профиля. Попробуй /start")

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
