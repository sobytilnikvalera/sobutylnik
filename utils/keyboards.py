from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton
)

def main_menu_kb():
    kb = [
        [KeyboardButton(text="🍻 Замутить движ"), KeyboardButton(text="🕵️ Ищу собутыльника")],
        [KeyboardButton(text="❤️ Мои матчи"), KeyboardButton(text="😎 Мой профиль")],
        [KeyboardButton(text="📜 Репутация"), KeyboardButton(text="📩 Написать админу")]
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
        [KeyboardButton(text="📍 Где я сейчас", request_location=True)],
        [KeyboardButton(text="◀️ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def confirm_kb():
    kb = [
        [InlineKeyboardButton(text="✅ Погнали!", callback_data="listing_confirm")],
        [InlineKeyboardButton(text="❌ Передумал", callback_data="listing_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def swipe_kb(listing_id):
    kb = [
        [
            InlineKeyboardButton(text="👎 Мимо", callback_data=f"swipe:dislike:{listing_id}"),
            InlineKeyboardButton(text="❤️ Лайк", callback_data=f"swipe:like:{listing_id}")
        ],
        [
            InlineKeyboardButton(text="🚩 Пожаловаться", callback_data=f"report:{listing_id}"),
            InlineKeyboardButton(text="🛑 Хватит на сегодня", callback_data="swipe:close")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def my_listing_actions_kb(listing_id):
    kb = [
        [InlineKeyboardButton(text="🔴 Удалить движ", callback_data=f"listing_close:{listing_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def rating_kb(meeting_id, to_user_id):
    kb = []
    for i in range(1, 6):
        kb.append(InlineKeyboardButton(text="⭐" * i, callback_data=f"review_rate:{meeting_id}:{to_user_id}:{i}"))
    return InlineKeyboardMarkup(inline_keyboard=[kb])
