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

def safe_send_content(current_bot, target_chat, content_type, text_content=None, file_id=None, caption=None, prefix="", message_thread_id=None):
    plain_prefix = prefix.replace("**", "").replace("*", "").replace("`", "").replace("_", "")
    
    if content_type == 'text':
        text_with_md = f"{prefix}{text_content or ''}"
        text_plain = f"{plain_prefix}{text_content or ''}"
        try:
            return current_bot.send_message(target_chat, text_with_md, parse_mode="Markdown", message_thread_id=message_thread_id)
        except Exception:
            return current_bot.send_message(target_chat, text_plain, message_thread_id=message_thread_id)
            
    elif content_type == 'photo':
        cap_md = f"{prefix}{caption or ''}"
        cap_plain = f"{plain_prefix}{caption or ''}"
        try:
            return current_bot.send_photo(target_chat, file_id, caption=cap_md, parse_mode="Markdown", message_thread_id=message_thread_id)
        except Exception:
            return current_bot.send_photo(target_chat, file_id, caption=cap_plain, message_thread_id=message_thread_id)
            
    elif content_type == 'document':
        cap_md = f"{prefix}{caption or ''}"
        cap_plain = f"{plain_prefix}{caption or ''}"
        try:
            return current_bot.send_document(target_chat, file_id, caption=cap_md, parse_mode="Markdown", message_thread_id=message_thread_id)
        except Exception:
            return current_bot.send_document(target_chat, file_id, caption=cap_plain, message_thread_id=message_thread_id)
            
    elif content_type == 'video':
        cap_md = f"{prefix}{caption or ''}"
        cap_plain = f"{plain_prefix}{caption or ''}"
        try:
            return current_bot.send_video(target_chat, file_id, caption=cap_md, parse_mode="Markdown", message_thread_id=message_thread_id)
        except Exception:
            return current_bot.send_video(target_chat, file_id, caption=cap_plain, message_thread_id=message_thread_id)
            
    elif content_type == 'voice':
        cap_md = f"{prefix}{caption or ''}"
        cap_plain = f"{plain_prefix}{caption or ''}"
        try:
            return current_bot.send_voice(target_chat, file_id, caption=cap_md, parse_mode="Markdown", message_thread_id=message_thread_id)
        except Exception:
            return current_bot.send_voice(target_chat, file_id, caption=cap_plain, message_thread_id=message_thread_id)
            
    elif content_type == 'audio':
        cap_md = f"{prefix}{caption or ''}"
        cap_plain = f"{plain_prefix}{caption or ''}"
        try:
            return current_bot.send_audio(target_chat, file_id, caption=cap_md, parse_mode="Markdown", message_thread_id=message_thread_id)
        except Exception:
            return current_bot.send_audio(target_chat, file_id, caption=cap_plain, message_thread_id=message_thread_id)