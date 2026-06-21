from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from typing import List, Dict


def main_menu_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📢 Создать объявление"),
        KeyboardButton(text="🔍 Найти собутыльника")
    )
    builder.row(
        KeyboardButton(text="📋 Мои объявления"),
        KeyboardButton(text="🤝 Мои встречи")
    )
    builder.row(
        KeyboardButton(text="👤 Мой профиль"),
        KeyboardButton(text="❓ Помощь")
    )
    return builder.as_markup(resize_keyboard=True)


def location_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📍 Отправить геолокацию", request_location=True))
    builder.row(KeyboardButton(text="◀️ Отмена"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="◀️ Отмена"))
    return builder.as_markup(resize_keyboard=True)


def confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Опубликовать", callback_data="listing_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="listing_cancel")
    )
    return builder.as_markup()


def listing_actions_kb(listing_id: int, is_owner: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_owner:
        builder.row(
            InlineKeyboardButton(text="👥 Заявки", callback_data=f"listing_requests:{listing_id}"),
            InlineKeyboardButton(text="🔴 Закрыть", callback_data=f"listing_close:{listing_id}")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="🙋 Хочу присоединиться", callback_data=f"listing_join:{listing_id}")
        )
    return builder.as_markup()


def join_request_kb(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Принять", callback_data=f"req_accept:{request_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"req_reject:{request_id}")
    )
    return builder.as_markup()


def meeting_actions_kb(meeting_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Завершить встречу", callback_data=f"meeting_complete:{meeting_id}")
    )
    return builder.as_markup()


def rating_kb(meeting_id: int, to_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        stars = "⭐" * i
        builder.add(InlineKeyboardButton(
            text=stars,
            callback_data=f"review_rate:{meeting_id}:{to_user_id}:{i}"
        ))
    builder.adjust(5)
    return builder.as_markup()


def skip_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="⏭ Пропустить"))
    builder.row(KeyboardButton(text="◀️ Отмена"))
    return builder.as_markup(resize_keyboard=True)


def listings_nav_kb(listings: List[Dict], current_idx: int) -> InlineKeyboardMarkup:
    """Клавиатура для навигации по объявлениям."""
    builder = InlineKeyboardBuilder()
    listing = listings[current_idx]
    listing_id = listing["id"]

    nav_row = []
    if current_idx > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"browse:{current_idx - 1}"))
    nav_row.append(InlineKeyboardButton(
        text=f"{current_idx + 1}/{len(listings)}",
        callback_data="browse_noop"
    ))
    if current_idx < len(listings) - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"browse:{current_idx + 1}"))

    builder.row(*nav_row)
    builder.row(
        InlineKeyboardButton(text="🙋 Хочу присоединиться", callback_data=f"listing_join:{listing_id}")
    )
    builder.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="browse_close"))
    return builder.as_markup()
