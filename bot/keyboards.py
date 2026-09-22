"""
Telegram Keyboards Builder
Generates Reply & Inline Keyboards for users and IT staff.
"""
from telebot import types

def get_report_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🚨 Báo sự cố mới", callback_data="reportIssue"),
        types.InlineKeyboardButton("🏢 Đổi phòng ban", callback_data="changeDept")
    )
    return markup

def get_rating_keyboard(ticket_id):
    markup = types.InlineKeyboardMarkup(row_width=5)
    buttons = [types.InlineKeyboardButton(f"{i} ⭐", callback_data=f"rate_{ticket_id}_{i}") for i in range(1, 6)]
    markup.add(*buttons)
    return markup
