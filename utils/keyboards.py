from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton
)

def main_menu_kb():
    kb = [
        [KeyboardButton(text="📢 Создать анкету"), KeyboardButton(text="🔍 Искать компанию")],
        [KeyboardButton(text="📋 Моя анкета"), KeyboardButton(text="⭐ Мои отзывы")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def cancel_kb():
    kb = [[KeyboardButton(text="◀️ Отмена")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def skip_kb():
    kb = [[KeyboardButton(text="⏭ Пропустить")], [KeyboardButton(text="◀️ Отмена")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def location_kb():
    kb = [
        [KeyboardButton(text="📍 Отправить геолокацию", request_location=True)],
        [KeyboardButton(text="◀️ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def confirm_kb():
    kb = [
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data="listing_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="listing_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def swipe_kb(listing_id):
    kb = [
        [
            InlineKeyboardButton(text="👎", callback_data=f"swipe:dislike:{listing_id}"),
            InlineKeyboardButton(text="❤️", callback_data=f"swipe:like:{listing_id}")
        ],
        [InlineKeyboardButton(text="🛑 Закончить просмотр", callback_data="swipe:close")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def my_listing_actions_kb(listing_id):
    kb = [
        [InlineKeyboardButton(text="🔴 Удалить анкету", callback_data=f"listing_close:{listing_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def rating_kb(meeting_id, to_user_id):
    kb = []
    for i in range(1, 6):
        kb.append(InlineKeyboardButton(text="⭐" * i, callback_data=f"review_rate:{meeting_id}:{to_user_id}:{i}"))
    return InlineKeyboardMarkup(inline_keyboard=[kb])
