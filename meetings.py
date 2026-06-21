from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database.db import (
    get_user, get_listing, create_join_request, get_join_request,
    get_pending_requests_for_listing, update_join_request_status,
    has_pending_request, create_meeting, get_meeting, get_user_meetings,
    complete_meeting, close_listing
)
from states.states import JoinRequest
from utils.keyboards import (
    main_menu_kb, cancel_kb, join_request_kb,
    meeting_actions_kb, listing_actions_kb
)
from utils.helpers import format_user_profile, format_meeting, stars

router = Router()


# ─── ОТКЛИК НА ОБЪЯВЛЕНИЕ ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("listing_join:"))
async def listing_join(callback: CallbackQuery, state: FSMContext):
    listing_id = int(callback.data.split(":")[1])
    listing = await get_listing(listing_id)

    if not listing:
        await callback.answer("Объявление не найдено.", show_alert=True)
        return

    if listing["status"] != "active":
        await callback.answer("Это объявление уже закрыто.", show_alert=True)
        return

    if listing["user_id"] == callback.from_user.id:
        await callback.answer("Это твоё объявление!", show_alert=True)
        return

    already = await has_pending_request(listing_id, callback.from_user.id)
    if already:
        await callback.answer("Ты уже откликнулся на это объявление.", show_alert=True)
        return

    await state.update_data(join_listing_id=listing_id)
    await callback.message.answer(
        f"🙋 Ты откликаешься на объявление *«{listing['title']}»*\n\n"
        f"Напиши короткое сообщение автору — представься, расскажи что можешь принести:\n"
        f"(или нажми «◀️ Отмена»)",
        parse_mode="Markdown",
        reply_markup=cancel_kb()
    )
    await state.set_state(JoinRequest.waiting_message)
    await callback.answer()


@router.message(JoinRequest.waiting_message)
async def process_join_message(message: Message, state: FSMContext, bot: Bot):
    if message.text == "◀️ Отмена":
        await state.clear()
        await message.answer("Отклик отменён.", reply_markup=main_menu_kb())
        return

    data = await state.get_data()
    listing_id = data.get("join_listing_id")
    await state.clear()

    if not listing_id:
        await message.answer("Что-то пошло не так. Попробуй снова.", reply_markup=main_menu_kb())
        return

    listing = await get_listing(listing_id)
    if not listing or listing["status"] != "active":
        await message.answer("Объявление уже недоступно.", reply_markup=main_menu_kb())
        return

    join_text = message.text.strip()[:500]
    request_id = await create_join_request(listing_id, message.from_user.id, join_text)

    await message.answer(
        "✅ Отклик отправлен! Ожидай ответа от автора объявления.",
        reply_markup=main_menu_kb()
    )

    # Уведомляем автора объявления
    user = await get_user(message.from_user.id)
    user_info = format_user_profile(user) if user else f"Пользователь {message.from_user.id}"

    notify_text = (
        f"🔔 *Новый отклик на твоё объявление!*\n\n"
        f"Объявление: *{listing['title']}*\n\n"
        f"*Кто откликнулся:*\n{user_info}\n\n"
        f"*Сообщение:*\n_{join_text}_"
    )

    try:
        await bot.send_message(
            listing["user_id"],
            notify_text,
            parse_mode="Markdown",
            reply_markup=join_request_kb(request_id)
        )
    except Exception:
        pass  # Пользователь мог заблокировать бота


# ─── ОБРАБОТКА ЗАЯВОК (ПРИНЯТЬ / ОТКЛОНИТЬ) ──────────────────────────────────

@router.callback_query(F.data.startswith("listing_requests:"))
async def show_requests(callback: CallbackQuery):
    listing_id = int(callback.data.split(":")[1])
    listing = await get_listing(listing_id)

    if not listing or listing["user_id"] != callback.from_user.id:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    requests = await get_pending_requests_for_listing(listing_id)
    if not requests:
        await callback.answer("Пока нет заявок.", show_alert=True)
        return

    for req in requests:
        name = req.get("first_name", "Аноним")
        username = f"@{req['username']}" if req.get("username") else ""
        rating = req.get("rating", 0.0)
        text = (
            f"👤 *{name}* {username}\n"
            f"⭐ {stars(rating)} ({rating:.1f})\n\n"
            f"💬 _{req.get('message', 'без сообщения')}_"
        )
        await callback.message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=join_request_kb(req["id"])
        )

    await callback.answer()


@router.callback_query(F.data.startswith("req_accept:"))
async def accept_request(callback: CallbackQuery, bot: Bot):
    request_id = int(callback.data.split(":")[1])
    req = await get_join_request(request_id)

    if not req:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    listing = await get_listing(req["listing_id"])
    if not listing or listing["user_id"] != callback.from_user.id:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    await update_join_request_status(request_id, "accepted")

    # Создаём встречу
    meeting_id = await create_meeting(
        listing_id=listing["id"],
        host_id=callback.from_user.id,
        guest_id=req["from_user_id"]
    )

    # Закрываем объявление
    await close_listing(listing["id"])

    await callback.message.edit_text(
        callback.message.text + f"\n\n✅ *Заявка принята! Встреча #{meeting_id} создана.*",
        parse_mode="Markdown"
    )

    # Уведомляем гостя
    host = await get_user(callback.from_user.id)
    host_name = host["first_name"] if host else "Хозяин"
    host_username = f"@{host['username']}" if host and host.get("username") else host_name

    try:
        await bot.send_message(
            req["from_user_id"],
            f"🎉 *Твой отклик принят!*\n\n"
            f"*{host_username}* принял твою заявку на объявление «{listing['title']}».\n\n"
            f"🤝 Встреча #{meeting_id} создана. Договоритесь о деталях в личке!\n\n"
            f"После встречи не забудьте завершить её в разделе «🤝 Мои встречи» и оставить отзывы.",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await callback.answer("Заявка принята! Встреча создана.")


@router.callback_query(F.data.startswith("req_reject:"))
async def reject_request(callback: CallbackQuery, bot: Bot):
    request_id = int(callback.data.split(":")[1])
    req = await get_join_request(request_id)

    if not req:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    listing = await get_listing(req["listing_id"])
    if not listing or listing["user_id"] != callback.from_user.id:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    await update_join_request_status(request_id, "rejected")
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ *Заявка отклонена.*",
        parse_mode="Markdown"
    )

    try:
        await bot.send_message(
            req["from_user_id"],
            f"😔 К сожалению, твой отклик на объявление «{listing['title']}» был отклонён.\n"
            f"Не расстраивайся — ищи другие объявления! 🔍"
        )
    except Exception:
        pass

    await callback.answer("Заявка отклонена.")


# ─── МОИ ВСТРЕЧИ ──────────────────────────────────────────────────────────────

@router.message(F.text == "🤝 Мои встречи")
@router.message(Command("meetings"))
async def cmd_my_meetings(message: Message, state: FSMContext):
    await state.clear()
    meetings = await get_user_meetings(message.from_user.id)

    if not meetings:
        await message.answer(
            "У тебя пока нет встреч.\n"
            "Найди объявление рядом или создай своё! 🍺",
            reply_markup=main_menu_kb()
        )
        return

    await message.answer(
        f"🤝 *Твои встречи* ({len(meetings)} шт.):",
        parse_mode="Markdown",
        reply_markup=main_menu_kb()
    )

    for meeting in meetings:
        text = format_meeting(meeting, message.from_user.id)
        kb = meeting_actions_kb(meeting["id"]) if meeting["status"] == "active" else None
        await message.answer(text, parse_mode="Markdown", reply_markup=kb)


@router.callback_query(F.data.startswith("meeting_complete:"))
async def complete_meeting_cb(callback: CallbackQuery, bot: Bot):
    meeting_id = int(callback.data.split(":")[1])
    meeting = await get_meeting(meeting_id)

    if not meeting:
        await callback.answer("Встреча не найдена.", show_alert=True)
        return

    if meeting["host_id"] != callback.from_user.id and meeting["guest_id"] != callback.from_user.id:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    if meeting["status"] != "active":
        await callback.answer("Встреча уже завершена.", show_alert=True)
        return

    await complete_meeting(meeting_id)
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ *Встреча завершена!*",
        parse_mode="Markdown"
    )

    # Просим обоих оставить отзыв
    other_id = meeting["guest_id"] if callback.from_user.id == meeting["host_id"] else meeting["host_id"]
    other_name = meeting["guest_name"] if callback.from_user.id == meeting["host_id"] else meeting["host_name"]

    review_prompt = (
        f"✅ Встреча #{meeting_id} завершена!\n\n"
        f"Пожалуйста, оставь отзыв о *{other_name}*.\n"
        f"Используй команду: /review_{meeting_id}"
    )

    await callback.message.answer(review_prompt, parse_mode="Markdown")

    try:
        my_name = meeting["host_name"] if callback.from_user.id == meeting["host_id"] else meeting["guest_name"]
        await bot.send_message(
            other_id,
            f"✅ Встреча #{meeting_id} завершена!\n\n"
            f"Пожалуйста, оставь отзыв о *{my_name}*.\n"
            f"Используй команду: /review_{meeting_id}",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await callback.answer("Встреча завершена!")
