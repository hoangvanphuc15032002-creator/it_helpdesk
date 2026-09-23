"""
Bot Runner & Supervisor Module
Initializes TeleBot instance, background watchdog threads, and polling loop.
"""
import threading
import time
import telebot
import config.settings as bot_config
from database.repository import init_db, get_config_from_db
from bot.handlers import setup_bot_handlers
from bot.tasks.auto_reminder import auto_remind_it
from bot.tasks.hub_sync import sync_hubs_with_db, sync_tickets_to_new_group

def run_bot_polling():
    while bot_config.is_running:
        try:
            if bot_config.bot:
                bot_config.bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
            time.sleep(2)  
        except Exception:
            if bot_config.is_running:
                time.sleep(5)

def config_watchdog():
    while bot_config.is_running:
        try:
            new_token, new_group_str, new_offset = get_config_from_db()
            if not new_token or new_token == 'ĐIỀN TOKEN VÀO ĐÂY':
                time.sleep(10)
                continue
                
            try:
                new_group = int(str(new_group_str).strip())
            except Exception:
                new_group = 0

            bot_config.TIME_OFFSET = new_offset

            if new_token != bot_config.TOKEN:
                if bot_config.bot:
                    try:
                        bot_config.bot.stop_polling()
                    except Exception:
                        pass
                    time.sleep(3) 
                bot_config.TOKEN = new_token
                bot_config.GROUP_IT_ID = new_group
                bot_config.bot = telebot.TeleBot(bot_config.TOKEN, num_threads=30)
                try:
                    bot_config.bot.remove_webhook()
                except Exception:
                    pass
                setup_bot_handlers(bot_config.bot)
                if bot_config.GROUP_IT_ID != 0:
                    sync_tickets_to_new_group(bot_config.bot, bot_config.GROUP_IT_ID)
                
            elif new_group != bot_config.GROUP_IT_ID:
                bot_config.GROUP_IT_ID = new_group
                if bot_config.bot and bot_config.GROUP_IT_ID != 0:
                    sync_tickets_to_new_group(bot_config.bot, bot_config.GROUP_IT_ID)
        except Exception as e:
            print(f"⚠️ Lỗi Watchdog Cấu hình: {e}")
        time.sleep(10) 

def start_bot():
    print("🚀 Khởi động Hệ thống Bot IT (Giữ ghim Tracker & Xóa rác tự động)...")
    init_db()
    threading.Thread(target=config_watchdog, daemon=True).start()
    threading.Thread(target=auto_remind_it, daemon=True).start()
    threading.Thread(target=sync_hubs_with_db, daemon=True).start()
    run_bot_polling()
