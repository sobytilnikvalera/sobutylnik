from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from database.db import get_user, create_user, update_user_profile, get_user_reviews
from states.states import ProfileSetup
from utils.keyboards import main_menu_kb, cancel_kb, skip_kb
from utils.helpers import format_user_profile, stars

router = Router()

WELCOME_TEXT = """
🍺 *Добро пожаловать в Собутыльник!*

Это сервис для поиска компании, чтобы скоротать вечер вместе.

Как это работает:
1️⃣ Создай объявление — укажи что есть выпить и где ты находишься
2️⃣ Или найди чужое объявление рядом с тобой
3️⃣ Договоритесь и встретьтесь
4️⃣ После встречи оставьте отзывы друг о друге

⚠️ *Важно:* Сервис только для совершеннолетних (18+). Пей ответственно!
"""


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
            parse_mode="Markdown",
            reply_markup=main_menu_kb()
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
        "✅ Профиль сохранён! Теперь можешь создавать объявления или искать компанию.",
        reply_markup=main_menu_kb()
    )


@router.message(F.text == "👤 Мой профиль")
@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext):
    await state.clear()
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйся — нажми /start")
        return

    text = format_user_profile(user)
    reviews = await get_user_reviews(message.from_user.id)

    if reviews:
        text += "\n\n*Последние отзывы:*\n"
        for r in reviews[:3]:
            author = r.get("author_name", "Аноним")
            text += f"\n{stars(r['rating'])} от *{author}*\n_{r.get('text', '') or 'без текста'}_\n"

    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu_kb())


@router.message(F.text == "❓ Помощь")
@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "🍺 *Собутыльник — помощь*\n\n"
        "📢 *Создать объявление* — расскажи что у тебя есть и где ты\n"
        "🔍 *Найти собутыльника* — посмотри объявления рядом\n"
        "📋 *Мои объявления* — управляй своими объявлениями\n"
        "🤝 *Мои встречи* — история встреч и отзывы\n"
        "👤 *Мой профиль* — твой профиль и рейтинг\n\n"
        "⚠️ *Правила:*\n"
        "• Только для совершеннолетних (18+)\n"
        "• Отзывы нельзя редактировать или удалять\n"
        "• Объявления автоматически истекают через 6 часов\n"
        "• Уважай других участников\n\n"
        "Пей ответственно! 🥃"
    )
    await message.answer(help_text, parse_mode="Markdown", reply_markup=main_menu_kb())
