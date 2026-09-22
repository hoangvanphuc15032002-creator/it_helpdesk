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

import math

def get_departments_keyboard(depts, page=1, per_page=6):
    markup = types.InlineKeyboardMarkup(row_width=1)
    total_depts = len(depts)
    if total_depts == 0:
        return markup
        
    total_pages = max(1, math.ceil(total_depts / per_page))
    page = max(1, min(page, total_pages))
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_depts = depts[start_idx:end_idx]
    
    for d_id, d_name in page_depts:
        markup.add(types.InlineKeyboardButton(d_name, callback_data=f"seldept_{d_id}"))
    
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(types.InlineKeyboardButton("⬅️ Trước", callback_data=f"deptpage_{page-1}"))
        else:
            nav_buttons.append(types.InlineKeyboardButton("⏹️", callback_data="noop"))
            
        if page < total_pages:
            nav_buttons.append(types.InlineKeyboardButton("Sau ➡️", callback_data=f"deptpage_{page+1}"))
        else:
            nav_buttons.append(types.InlineKeyboardButton("⏹️", callback_data="noop"))
            
        markup.row(*nav_buttons)
        
    return markup

def get_departments_reply_keyboard(depts):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, row_width=2)
    buttons = [types.KeyboardButton(d_name) for _, d_name in depts]
    markup.add(*buttons)
    return markup

def send_department_chunks(bot, chat_id, user_name, depts, chunk_size=15):
    total_depts = len(depts)
    if total_depts == 0:
        bot.send_message(chat_id, f"👋 Chào {user_name}! 🏢 Nhập tên Phòng ban của bạn:")
        return

    chunks = [depts[i:i + chunk_size] for i in range(0, total_depts, chunk_size)]
    total_chunks = len(chunks)

    for idx, chunk in enumerate(chunks, 1):
        markup = types.InlineKeyboardMarkup(row_width=1)
        for d_id, d_name in chunk:
            markup.add(types.InlineKeyboardButton(d_name, callback_data=f"seldept_{d_id}"))
        
        if total_chunks > 1:
            header = f"🏢 **Vui lòng chọn Phòng ban của bạn (Danh sách {idx}/{total_chunks}):**"
        else:
            header = f"🏢 **Vui lòng chọn Phòng ban của bạn bên dưới:**"
            
        if idx == 1:
            header = f"👋 Chào **{user_name}**!\n\n" + header

        try:
            bot.send_message(chat_id, header, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            header_clean = header.replace("**", "").replace("*", "")
            bot.send_message(chat_id, header_clean, reply_markup=markup)
