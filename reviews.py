import re
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database.db import (
    get_user, get_meeting, create_review, has_review, get_user_reviews
)
from states.states import LeaveReview
from utils.keyboards import main_menu_kb, cancel_kb, rating_kb, skip_kb
from utils.helpers import stars

router = Router()


# ─── ОСТАВИТЬ ОТЗЫВ ───────────────────────────────────────────────────────────

@router.message(F.text.regexp(r'^/review_(\d+)$'))
async def cmd_review(message: Message, state: FSMContext):
    match = re.match(r'^/review_(\d+)$', message.text)
    meeting_id = int(match.group(1))

    meeting = await get_meeting(meeting_id)
    if not meeting:
        await message.answer("Встреча не найдена.", reply_markup=main_menu_kb())
        return

    user_id = message.from_user.id
    if meeting["host_id"] != user_id and meeting["guest_id"] != user_id:
        await message.answer("У тебя нет доступа к этой встрече.", reply_markup=main_menu_kb())
        return

    if meeting["status"] != "completed":
        await message.answer(
            "Встреча ещё не завершена. Сначала завери её в разделе «🤝 Мои встречи».",
            reply_markup=main_menu_kb()
        )
        return

    already = await has_review(meeting_id, user_id)
    if already:
        await message.answer(
            "⚠️ Ты уже оставил отзыв об этой встрече.\n"
            "Отзывы нельзя редактировать или удалять.",
            reply_markup=main_menu_kb()
        )
        return

    to_user_id = meeting["guest_id"] if user_id == meeting["host_id"] else meeting["host_id"]
    to_user_name = meeting["guest_name"] if user_id == meeting["host_id"] else meeting["host_name"]

    await state.update_data(meeting_id=meeting_id, to_user_id=to_user_id, to_user_name=to_user_name)

    await message.answer(
        f"⭐ *Оставь отзыв о {to_user_name}*\n\n"
        f"Выбери оценку от 1 до 5:",
        parse_mode="Markdown",
        reply_markup=rating_kb(meeting_id, to_user_id)
    )
    await state.set_state(LeaveReview.waiting_rating)


@router.callback_query(F.data.startswith("review_rate:"))
async def process_rating(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    meeting_id = int(parts[1])
    to_user_id = int(parts[2])
    rating = int(parts[3])

    current_state = await state.get_state()
    if current_state != LeaveReview.waiting_rating.state:
        # Повторный клик — игнорируем
        await callback.answer()
        return

    data = await state.get_data()
    to_user_name = data.get("to_user_name", "пользователя")

    await state.update_data(rating=rating)
    await callback.message.edit_text(
        f"⭐ Оценка: *{stars(rating)}* ({rating}/5)\n\n"
        f"Теперь напиши текст отзыва о *{to_user_name}*.\n"
        f"Расскажи как прошла встреча, был ли человек приятным собеседником.\n\n"
        f"_(или нажми «Пропустить» — но лучше написать!)_",
        parse_mode="Markdown"
    )
    await callback.message.answer("Напиши отзыв:", reply_markup=skip_kb())
    await state.set_state(LeaveReview.waiting_text)
    await callback.answer()


@router.message(LeaveReview.waiting_text)
async def process_review_text(message: Message, state: FSMContext, bot: Bot):
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Отзыв отменён.", reply_markup=main_menu_kb())
        return

    review_text = "" if message.text == "⏭ Пропустить" else message.text.strip()[:1000]
    data = await state.get_data()
    await state.clear()

    meeting_id = data.get("meeting_id")
    to_user_id = data.get("to_user_id")
    to_user_name = data.get("to_user_name", "пользователя")
    rating = data.get("rating", 5)

    if not meeting_id or not to_user_id:
        await message.answer("Что-то пошло не так. Попробуй снова.", reply_markup=main_menu_kb())
        return

    # Проверяем ещё раз — вдруг уже оставил
    already = await has_review(meeting_id, message.from_user.id)
    if already:
        await message.answer(
            "⚠️ Ты уже оставил отзыв. Отзывы нельзя редактировать или удалять.",
            reply_markup=main_menu_kb()
        )
        return

    await create_review(
        meeting_id=meeting_id,
        from_user_id=message.from_user.id,
        to_user_id=to_user_id,
        rating=rating,
        text=review_text
    )

    await message.answer(
        f"✅ *Отзыв сохранён!*\n\n"
        f"Оценка: {stars(rating)} ({rating}/5)\n"
        f"О: *{to_user_name}*\n"
        f"Текст: _{review_text or 'без текста'}_\n\n"
        f"⚠️ Отзыв нельзя редактировать или удалять — это гарантирует честность системы.",
        parse_mode="Markdown",
        reply_markup=main_menu_kb()
    )

    # Уведомляем получателя отзыва
    author = await get_user(message.from_user.id)
    author_name = author["first_name"] if author else "Кто-то"

    try:
        notify = (
            f"🔔 *Новый отзыв о тебе!*\n\n"
            f"От: *{author_name}*\n"
            f"Оценка: {stars(rating)} ({rating}/5)\n"
        )
        if review_text:
            notify += f"Текст: _{review_text}_"
        await bot.send_message(to_user_id, notify, parse_mode="Markdown")
    except Exception:
        pass


# ─── ПРОСМОТР ОТЗЫВОВ ─────────────────────────────────────────────────────────

@router.message(Command("reviews"))
async def cmd_reviews(message: Message):
    reviews = await get_user_reviews(message.from_user.id)
    user = await get_user(message.from_user.id)

    if not reviews:
        await message.answer(
            "У тебя пока нет отзывов.\n"
            "Встречайся с людьми и получай отзывы! 🍺",
            reply_markup=main_menu_kb()
        )
        return

    avg = user["rating"] if user else 0.0
    count = user["reviews_count"] if user else 0

    text = (
        f"⭐ *Твои отзывы*\n"
        f"Средняя оценка: {stars(avg)} ({avg:.1f} из {count} отзывов)\n\n"
    )

    for r in reviews[:10]:
        author = r.get("author_name", "Аноним")
        author_u = f"@{r['author_username']}" if r.get("author_username") else ""
        review_text = r.get("text") or "_без текста_"
        text += (
            f"{'─' * 20}\n"
            f"{stars(r['rating'])} от *{author}* {author_u}\n"
            f"_{review_text}_\n"
        )

    text += "\n⚠️ _Отзывы нельзя редактировать или удалять._"
    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu_kb())
