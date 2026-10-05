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
    
    for item in page_depts:
        if isinstance(item, (list, tuple)):
            d_id = item[0]
            d_name = item[1] if len(item) > 1 else item[0]
        else:
            d_id = item
            d_name = item
        markup.add(types.InlineKeyboardButton(str(d_name), callback_data=f"seldept_{d_id}"))
    
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(types.InlineKeyboardButton("⬅️ Trước", callback_data=f"deptpage_{page-1}"))
        else:
            nav_buttons.append(types.InlineKeyboardButton("⏹️", callback_data="noop"))
            
        nav_buttons.append(types.InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop"))

        if page < total_pages:
            nav_buttons.append(types.InlineKeyboardButton("Sau ➡️", callback_data=f"deptpage_{page+1}"))
        else:
            nav_buttons.append(types.InlineKeyboardButton("⏹️", callback_data="noop"))
            
        markup.row(*nav_buttons)
        
    return markup

def get_departments_reply_keyboard(depts):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, row_width=2)
    buttons = []
    for item in depts:
        d_name = item[1] if isinstance(item, (list, tuple)) and len(item) > 1 else (item[0] if isinstance(item, (list, tuple)) else item)
        buttons.append(types.KeyboardButton(str(d_name)))
    markup.add(*buttons)
    return markup

def send_department_chunks(bot, chat_id, user_name, depts, chunk_size=6):
    total_depts = len(depts)
    sent_msg_ids = []
    if total_depts == 0:
        try:
            msg = bot.send_message(chat_id, f"👋 Chào **{user_name}**!\n🏢 Nhập tên Phòng ban của bạn:", parse_mode="Markdown")
            if msg: sent_msg_ids.append(msg.message_id)
        except Exception:
            msg = bot.send_message(chat_id, f"👋 Chào {user_name}!\n🏢 Nhập tên Phòng ban của bạn:")
            if msg: sent_msg_ids.append(msg.message_id)
        return sent_msg_ids

    markup = get_departments_keyboard(depts, page=1, per_page=chunk_size)
    header = f"👋 Chào **{user_name}**!\n\n🏢 **Vui lòng chọn Phòng ban của bạn bên dưới:**"

    try:
        sent_msg = bot.send_message(chat_id, header, reply_markup=markup, parse_mode="Markdown")
        if sent_msg:
            sent_msg_ids.append(sent_msg.message_id)
    except Exception:
        header_clean = f"👋 Chào {user_name}!\n\n🏢 Vui lòng chọn Phòng ban của bạn bên dưới:"
        try:
            sent_msg = bot.send_message(chat_id, header_clean, reply_markup=markup)
            if sent_msg:
                sent_msg_ids.append(sent_msg.message_id)
        except Exception:
            pass

    return sent_msg_ids
