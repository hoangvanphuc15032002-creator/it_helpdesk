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

def get_departments_keyboard(depts, page=1, per_page=10):
    markup = types.InlineKeyboardMarkup(row_width=2)
    total_depts = len(depts)
    if total_depts == 0:
        return markup
        
    total_pages = max(1, math.ceil(total_depts / per_page))
    page = max(1, min(page, total_pages))
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_depts = depts[start_idx:end_idx]
    
    buttons = [types.InlineKeyboardButton(d_name, callback_data=f"seldept_{d_id}") for d_id, d_name in page_depts]
    markup.add(*buttons)
    
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
