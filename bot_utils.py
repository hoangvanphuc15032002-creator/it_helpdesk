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

def truncate_text(text, max_len=4000, suffix="... (nội dung xem thêm trên Web)"):
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len - len(suffix)] + suffix

def safe_edit_message(current_bot, chat_id, message_id, new_text, reply_markup=None):
    try:
        msg_id = int(message_id)
        text_md = truncate_text(new_text, 4000)
        text_plain = truncate_text(new_text.replace("**", "").replace("*", "").replace("`", "").replace("_", ""), 4000)
        
        cap_md = truncate_text(new_text, 1000)
        cap_plain = truncate_text(new_text.replace("**", "").replace("*", "").replace("`", "").replace("_", ""), 1000)

        try: current_bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text_md, parse_mode="Markdown", reply_markup=reply_markup)
        except:
            try: current_bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text_plain, reply_markup=reply_markup)
            except:
                try: current_bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=cap_md, parse_mode="Markdown", reply_markup=reply_markup)
                except:
                    try: current_bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=cap_plain, reply_markup=reply_markup)
                    except:
                        try: current_bot.send_message(chat_id, f"🔄 **CẬP NHẬT TRẠNG THÁI MỚI:**\n\n{text_md}", reply_to_message_id=msg_id, parse_mode="Markdown", reply_markup=reply_markup)
                        except:
                            try: current_bot.send_message(chat_id, f"🔄 CẬP NHẬT TRẠNG THÁI MỚI:\n\n{text_plain}", reply_to_message_id=msg_id, reply_markup=reply_markup)
                            except: pass
    except: pass

def safe_send_content(current_bot, target_chat, content_type, text_content=None, file_id=None, caption=None, prefix="", message_thread_id=None):
    plain_prefix = prefix.replace("**", "").replace("*", "").replace("`", "").replace("_", "")
    
    if content_type == 'text':
        text_with_md = truncate_text(f"{prefix}{text_content or ''}", 4000)
        text_plain = truncate_text(f"{plain_prefix}{text_content or ''}", 4000)
        try:
            return current_bot.send_message(target_chat, text_with_md, parse_mode="Markdown", message_thread_id=message_thread_id)
        except Exception:
            return current_bot.send_message(target_chat, text_plain, message_thread_id=message_thread_id)
            
    elif content_type == 'photo':
        cap_md = truncate_text(f"{prefix}{caption or ''}", 1000)
        cap_plain = truncate_text(f"{plain_prefix}{caption or ''}", 1000)
        try:
            return current_bot.send_photo(target_chat, file_id, caption=cap_md, parse_mode="Markdown", message_thread_id=message_thread_id)
        except Exception:
            try:
                return current_bot.send_photo(target_chat, file_id, caption=cap_plain, message_thread_id=message_thread_id)
            except Exception:
                return safe_send_content(current_bot, target_chat, 'text', text_content=caption, prefix=prefix, message_thread_id=message_thread_id)
            
    elif content_type == 'document':
        cap_md = truncate_text(f"{prefix}{caption or ''}", 1000)
        cap_plain = truncate_text(f"{plain_prefix}{caption or ''}", 1000)
        try:
            return current_bot.send_document(target_chat, file_id, caption=cap_md, parse_mode="Markdown", message_thread_id=message_thread_id)
        except Exception:
            try:
                return current_bot.send_document(target_chat, file_id, caption=cap_plain, message_thread_id=message_thread_id)
            except Exception:
                return safe_send_content(current_bot, target_chat, 'text', text_content=caption, prefix=prefix, message_thread_id=message_thread_id)
            
    elif content_type == 'video':
        cap_md = truncate_text(f"{prefix}{caption or ''}", 1000)
        cap_plain = truncate_text(f"{plain_prefix}{caption or ''}", 1000)
        try:
            return current_bot.send_video(target_chat, file_id, caption=cap_md, parse_mode="Markdown", message_thread_id=message_thread_id)
        except Exception:
            try:
                return current_bot.send_video(target_chat, file_id, caption=cap_plain, message_thread_id=message_thread_id)
            except Exception:
                return safe_send_content(current_bot, target_chat, 'text', text_content=caption, prefix=prefix, message_thread_id=message_thread_id)
            
    elif content_type == 'voice':
        cap_md = truncate_text(f"{prefix}{caption or ''}", 1000)
        cap_plain = truncate_text(f"{plain_prefix}{caption or ''}", 1000)
        try:
            return current_bot.send_voice(target_chat, file_id, caption=cap_md, parse_mode="Markdown", message_thread_id=message_thread_id)
        except Exception:
            try:
                return current_bot.send_voice(target_chat, file_id, caption=cap_plain, message_thread_id=message_thread_id)
            except Exception:
                return safe_send_content(current_bot, target_chat, 'text', text_content=caption, prefix=prefix, message_thread_id=message_thread_id)
            
    elif content_type == 'audio':
        cap_md = truncate_text(f"{prefix}{caption or ''}", 1000)
        cap_plain = truncate_text(f"{plain_prefix}{caption or ''}", 1000)
        try:
            return current_bot.send_audio(target_chat, file_id, caption=cap_md, parse_mode="Markdown", message_thread_id=message_thread_id)
        except Exception:
            try:
                return current_bot.send_audio(target_chat, file_id, caption=cap_plain, message_thread_id=message_thread_id)
            except Exception:
                return safe_send_content(current_bot, target_chat, 'text', text_content=caption, prefix=prefix, message_thread_id=message_thread_id)

def send_ticket_to_group(current_bot, target_chat, content_type, file_id, text, reply_markup=None):
    plain_text = text.replace("**", "").replace("*", "").replace("`", "").replace("_", "")
    
    text_md_4000 = truncate_text(text, 4000)
    text_plain_4000 = truncate_text(plain_text, 4000)
    
    cap_md_1000 = truncate_text(text, 1000)
    cap_plain_1000 = truncate_text(plain_text, 1000)
    
    if content_type == 'photo':
        try:
            return current_bot.send_photo(target_chat, file_id, caption=cap_md_1000, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception:
            try:
                return current_bot.send_photo(target_chat, file_id, caption=cap_plain_1000, reply_markup=reply_markup)
            except Exception:
                pass
    elif content_type == 'video':
        try:
            return current_bot.send_video(target_chat, file_id, caption=cap_md_1000, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception:
            try:
                return current_bot.send_video(target_chat, file_id, caption=cap_plain_1000, reply_markup=reply_markup)
            except Exception:
                pass
    elif content_type == 'document':
        try:
            return current_bot.send_document(target_chat, file_id, caption=cap_md_1000, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception:
            try:
                return current_bot.send_document(target_chat, file_id, caption=cap_plain_1000, reply_markup=reply_markup)
            except Exception:
                pass
    elif content_type == 'voice':
        try:
            return current_bot.send_voice(target_chat, file_id, caption=cap_md_1000, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception:
            try:
                return current_bot.send_voice(target_chat, file_id, caption=cap_plain_1000, reply_markup=reply_markup)
            except Exception:
                pass
    elif content_type == 'audio':
        try:
            return current_bot.send_audio(target_chat, file_id, caption=cap_md_1000, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception:
            try:
                return current_bot.send_audio(target_chat, file_id, caption=cap_plain_1000, reply_markup=reply_markup)
            except Exception:
                pass

    # Fallback to text message if media failed or content_type is text
    try:
        return current_bot.send_message(target_chat, text_md_4000, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception:
        try:
            return current_bot.send_message(target_chat, text_plain_4000, reply_markup=reply_markup)
        except Exception:
            return None
