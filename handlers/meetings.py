from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database.db import (
    get_user, create_meeting, get_meeting, get_user_meetings,
    complete_meeting
)
from utils.keyboards import main_menu_kb

router = Router()

# ─── МОИ ВСТРЕЧИ ──────────────────────────────────────────────────────────────
# В новой системе встречи создаются автоматически при взаимном лайке.

@router.message(F.text == "🤝 Мои встречи")
@router.message(Command("meetings"))
async def cmd_my_meetings(message: Message, state: FSMContext):
    await state.clear()
    meetings = await get_user_meetings(message.from_user.id)

    if not meetings:
        await message.answer(
            "У тебя пока нет завершенных встреч.\n"
            "Ищи компанию через поиск! ❤️",
            reply_markup=main_menu_kb()
        )
        return

    text = f"🤝 *Твои встречи* ({len(meetings)} шт.):\n"
    for m in meetings:
        status = "✅ Завершена" if m['status'] == 'completed' else "🟢 Активна"
        text += f"\nВстреча #{m['id']} - {status}"
    
    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu_kb())
