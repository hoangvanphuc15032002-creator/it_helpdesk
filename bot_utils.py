from telebot import types
from datetime import datetime, timedelta
import bot_config

def get_adjusted_time():
    return datetime.now() + timedelta(seconds=bot_config.TIME_OFFSET)

def get_rating_keyboard(ticket_id):
    markup = types.InlineKeyboardMarkup()
    btns = [types.InlineKeyboardButton(f"{i} ⭐", callback_data=f"rate_{ticket_id}_{i}") for i in range(1, 6)]
    markup.row(*btns)
    return markup

def get_report_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🚨 Báo sự cố mới", callback_data="reportIssue"),
        types.InlineKeyboardButton("🔄 Đổi phòng ban", callback_data="changeDept")
    )
    return markup

def safe_edit_message(current_bot, chat_id, message_id, new_text, reply_markup=None):
    try:
        msg_id = int(message_id)
        try: current_bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=new_text, parse_mode="Markdown", reply_markup=reply_markup)
        except:
            try: current_bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=new_text, parse_mode="Markdown", reply_markup=reply_markup)
            except:
                try: current_bot.send_message(chat_id, f"🔄 **CẬP NHẬT TRẠNG THÁI MỚI:**\n\n{new_text}", reply_to_message_id=msg_id, parse_mode="Markdown", reply_markup=reply_markup)
                except: pass
    except: pass