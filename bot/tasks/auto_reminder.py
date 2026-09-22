"""
Background Task: Auto Reminder for IT Staff
Sends emergency reminders for tickets waiting longer than 15 minutes.
"""
import time
from datetime import timedelta
import config.settings as bot_config
from database.connection import connect_db
from utils.helpers import get_adjusted_time

notified_tickets = set()

def auto_remind_it():
    while bot_config.is_running:
        try:
            time.sleep(60) 
            if not bot_config.bot or not bot_config.GROUP_IT_ID:
                continue
            conn = connect_db()
            try:
                cursor = conn.cursor()
                fifteen_mins_ago = (get_adjusted_time() - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("SELECT id FROM tickets WHERE status = 'Mới' AND created_at < ?", (fifteen_mins_ago,))
                rows = cursor.fetchall()
            finally:
                conn.close()
            
            to_notify = []
            for r in rows:
                if r[0] not in notified_tickets:
                    to_notify.append(r[0])
                    notified_tickets.add(r[0]) 
            
            if len(notified_tickets) > 1000:
                notified_tickets.clear()
                    
            if to_notify:
                ids = ", ".join([f"#{tid}" for tid in to_notify])
                if bot_config.last_reminder_msg_id:
                    try:
                        bot_config.bot.delete_message(bot_config.GROUP_IT_ID, bot_config.last_reminder_msg_id)
                    except Exception:
                        pass
                msg = bot_config.bot.send_message(
                    bot_config.GROUP_IT_ID,
                    f"📢 **THÔNG BÁO NHẮC VIỆC KHẨN CẤP!**\n\nCác sự cố {ids} đã treo hơn 15 phút. Anh em kiểm tra gấp! 🔥",
                    parse_mode="Markdown"
                )
                bot_config.last_reminder_msg_id = msg.message_id 
        except Exception:
            pass
