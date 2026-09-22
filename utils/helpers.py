"""
Utility Helper Functions
Provides time offset adjustment, text truncation, safe Telegram message sending & editing.
"""
from datetime import datetime, timedelta
import config.settings as bot_config

def get_adjusted_time():
    return datetime.now() + timedelta(seconds=bot_config.TIME_OFFSET)

def truncate_text(text, max_length=4000):
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - 15] + "\n\n[...Cắt ngắn]"

def safe_edit_message(current_bot, chat_id, message_id, new_text, reply_markup=None):
    if not current_bot or not chat_id or not message_id:
        return
    plain_text = new_text.replace("**", "").replace("*", "").replace("`", "").replace("_", "")
    try:
        current_bot.edit_message_text(new_text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception:
        try:
            current_bot.edit_message_text(plain_text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)
        except Exception:
            pass

def safe_send_content(current_bot, target_chat, content_type, text_content=None, file_id=None, caption=None, prefix="", message_thread_id=None):
    plain_prefix = prefix.replace("**", "").replace("*", "").replace("`", "").replace("_", "")
    
    if content_type in ['sticker', 'video_note', 'animation', 'location', 'contact']:
        try:
            if prefix:
                current_bot.send_message(target_chat, prefix, parse_mode="Markdown", message_thread_id=message_thread_id)
        except Exception:
            try:
                if plain_prefix:
                    current_bot.send_message(target_chat, plain_prefix, message_thread_id=message_thread_id)
            except Exception:
                pass

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

    elif content_type in ['video', 'audio', 'voice']:
        cap_md = truncate_text(f"{prefix}{caption or ''}", 1000)
        cap_plain = truncate_text(f"{plain_prefix}{caption or ''}", 1000)
        try:
            if content_type == 'video':
                return current_bot.send_video(target_chat, file_id, caption=cap_md, parse_mode="Markdown", message_thread_id=message_thread_id)
            elif content_type == 'audio':
                return current_bot.send_audio(target_chat, file_id, caption=cap_md, parse_mode="Markdown", message_thread_id=message_thread_id)
            elif content_type == 'voice':
                return current_bot.send_voice(target_chat, file_id, caption=cap_md, parse_mode="Markdown", message_thread_id=message_thread_id)
        except Exception:
            try:
                if content_type == 'video':
                    return current_bot.send_video(target_chat, file_id, caption=cap_plain, message_thread_id=message_thread_id)
                elif content_type == 'audio':
                    return current_bot.send_audio(target_chat, file_id, caption=cap_plain, message_thread_id=message_thread_id)
                elif content_type == 'voice':
                    return current_bot.send_voice(target_chat, file_id, caption=cap_plain, message_thread_id=message_thread_id)
            except Exception:
                return safe_send_content(current_bot, target_chat, 'text', text_content=caption, prefix=prefix, message_thread_id=message_thread_id)

    elif content_type == 'sticker':
        try:
            return current_bot.send_sticker(target_chat, file_id, message_thread_id=message_thread_id)
        except Exception:
            pass

    elif content_type == 'animation':
        cap_md = truncate_text(f"{prefix}{caption or ''}", 1000)
        cap_plain = truncate_text(f"{plain_prefix}{caption or ''}", 1000)
        try:
            return current_bot.send_animation(target_chat, file_id, caption=cap_md, parse_mode="Markdown", message_thread_id=message_thread_id)
        except Exception:
            try:
                return current_bot.send_animation(target_chat, file_id, caption=cap_plain, message_thread_id=message_thread_id)
            except Exception:
                pass

    elif content_type == 'video_note':
        try:
            return current_bot.send_video_note(target_chat, file_id, message_thread_id=message_thread_id)
        except Exception:
            pass

def send_ticket_to_group(current_bot, target_chat, content_type, file_id, text, reply_markup=None):
    plain_text = text.replace("**", "").replace("*", "").replace("`", "").replace("_", "")
    
    if file_id and content_type == 'photo':
        try:
            return current_bot.send_photo(target_chat, file_id, caption=truncate_text(text, 1000), reply_markup=reply_markup, parse_mode="Markdown")
        except Exception:
            try:
                return current_bot.send_photo(target_chat, file_id, caption=truncate_text(plain_text, 1000), reply_markup=reply_markup)
            except Exception:
                pass

    elif file_id and content_type == 'document':
        try:
            return current_bot.send_document(target_chat, file_id, caption=truncate_text(text, 1000), reply_markup=reply_markup, parse_mode="Markdown")
        except Exception:
            try:
                return current_bot.send_document(target_chat, file_id, caption=truncate_text(plain_text, 1000), reply_markup=reply_markup)
            except Exception:
                pass

    elif file_id and content_type in ['video', 'audio', 'voice']:
        try:
            if content_type == 'video':
                return current_bot.send_video(target_chat, file_id, caption=truncate_text(text, 1000), reply_markup=reply_markup, parse_mode="Markdown")
            elif content_type == 'audio':
                return current_bot.send_audio(target_chat, file_id, caption=truncate_text(text, 1000), reply_markup=reply_markup, parse_mode="Markdown")
            elif content_type == 'voice':
                return current_bot.send_voice(target_chat, file_id, caption=truncate_text(text, 1000), reply_markup=reply_markup, parse_mode="Markdown")
        except Exception:
            try:
                if content_type == 'video':
                    return current_bot.send_video(target_chat, file_id, caption=truncate_text(plain_text, 1000), reply_markup=reply_markup)
                elif content_type == 'audio':
                    return current_bot.send_audio(target_chat, file_id, caption=truncate_text(plain_text, 1000), reply_markup=reply_markup)
                elif content_type == 'voice':
                    return current_bot.send_voice(target_chat, file_id, caption=truncate_text(plain_text, 1000), reply_markup=reply_markup)
            except Exception:
                pass

    # Fallback sending plain text message
    try:
        return current_bot.send_message(target_chat, truncate_text(text, 4000), reply_markup=reply_markup, parse_mode="Markdown")
    except Exception:
        return current_bot.send_message(target_chat, truncate_text(plain_text, 4000), reply_markup=reply_markup)
