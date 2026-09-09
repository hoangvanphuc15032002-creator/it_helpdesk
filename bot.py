import threading
import time
import telebot
from telebot import types
from datetime import timedelta

import bot_config
from bot_db import init_db, connect_db, get_config_from_db
from bot_utils import get_adjusted_time, safe_edit_message, get_rating_keyboard, get_report_keyboard, truncate_text
from bot_handlers import setup_bot_handlers

def sync_tickets_to_new_group(current_bot, new_group_id):
    if not current_bot or not new_group_id: return
    conn = connect_db()
    try:
        cursor = conn.cursor()
        row = cursor.execute("SELECT value FROM settings WHERE key='LAST_SYNCED_GROUP_ID'").fetchone()
        last_synced = row[0].strip() if row else None
        
        if str(new_group_id) == last_synced:
            return
            
        print(f"🔄 Phát hiện thay đổi Nhóm IT sang ID: {new_group_id}. Đang quét & bắn lại Ticket...")
        try: current_bot.send_message(new_group_id, "🔄 **HỆ THỐNG ĐANG ĐỒNG BỘ DỮ LIỆU...**", parse_mode="Markdown")
        except Exception as e:
            print(f"❌ Lỗi gửi thông báo (Kiểm tra lại xem Bot đã thêm vào nhóm chưa): {e}")
            return

        cursor.execute("SELECT id, status, user_name, dept, issue, it_name, support_it_names FROM tickets WHERE status != 'Hoàn thành' ORDER BY id ASC")
        active_tickets = cursor.fetchall()
        
        synced_count = 0
        for r in active_tickets:
            t_id, status, user_name, dept, issue, it_name, support_it_names = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
            short_issue = truncate_text(issue, 3000)
            try:
                if status == 'Mới':
                    text_new = f"🚨 **YÊU CẦU #{t_id} (ĐANG CHỜ TIẾP NHẬN)**\n👤 Khách: {user_name}\n🏢 Phòng: {dept}\n📝 Lỗi: {short_issue}"
                    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤝 Nhận việc (Làm chính)", callback_data=f"claim_{t_id}"))
                    try:
                        sent_msg = current_bot.send_message(new_group_id, text_new, reply_markup=markup, parse_mode="Markdown")
                    except Exception:
                        sent_msg = current_bot.send_message(new_group_id, text_new.replace("**", "").replace("*", "").replace("`", "").replace("_", ""), reply_markup=markup)
                    
                    if sent_msg:
                        try: current_bot.pin_chat_message(chat_id=new_group_id, message_id=sent_msg.message_id, disable_notification=True)
                        except: pass
                        cursor.execute("UPDATE tickets SET group_msg_id = ? WHERE id = ?", (sent_msg.message_id, t_id))
                        synced_count += 1
                elif status == 'Đang xử lý':
                    sup_text = f"\n👨‍🔧 **Hỗ trợ:** {support_it_names}" if support_it_names else ""
                    text_proc = f"🚨 **YÊU CẦU #{t_id}**\n👤 Khách: {user_name}\n🏢 Phòng: {dept}\n📝 Lỗi: {short_issue}\n\n⏳ **Đang xử lý**\n👨‍💻 **IT Chính:** {it_name or 'N/A'}{sup_text}"
                    try:
                        sent_msg = current_bot.send_message(new_group_id, text_proc, parse_mode="Markdown")
                    except Exception:
                        sent_msg = current_bot.send_message(new_group_id, text_proc.replace("**", "").replace("*", "").replace("`", "").replace("_", ""))
                    
                    if sent_msg:
                        try: current_bot.pin_chat_message(chat_id=new_group_id, message_id=sent_msg.message_id, disable_notification=True)
                        except: pass
                        cursor.execute("UPDATE tickets SET group_msg_id = ? WHERE id = ?", (sent_msg.message_id, t_id))
                        synced_count += 1
            except Exception as ex: print(f"⚠️ Lỗi khi bắn Ticket #{t_id}: {ex}")

        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('LAST_SYNCED_GROUP_ID', ?)", (str(new_group_id),))
        conn.commit()
    finally:
        conn.close()

    try: current_bot.send_message(new_group_id, f"✅ **ĐỒNG BỘ HOÀN TẤT!**\nChuyển tiếp lại **{synced_count}** Ticket.", parse_mode="Markdown")
    except: pass

last_checked_update_ts = None

def sync_hubs_with_db():
    global last_checked_update_ts
    try:
        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, status, user_name, dept, issue, it_name, support_it_names, it_id FROM tickets WHERE status != 'Hoàn thành'")
            for row in cursor.fetchall():
                bot_config.ticket_last_status[row[0]] = (row[1], row[2], row[3], row[4], row[5], row[6], row[7])
            
            row_ts = cursor.execute("SELECT value FROM settings WHERE key='LAST_TICKET_UPDATE'").fetchone()
            last_checked_update_ts = row_ts[0] if row_ts else None
        finally:
            conn.close()
    except: pass
    
    while bot_config.is_running:
        try:
            time.sleep(3)
            conn = connect_db()
            try:
                cursor = conn.cursor()
                
                # Kiểm tra mốc thời gian xem Web có thay đổi ticket nào không
                row_ts = cursor.execute("SELECT value FROM settings WHERE key='LAST_TICKET_UPDATE'").fetchone()
                current_ts = row_ts[0] if row_ts else None
                
                if current_ts == last_checked_update_ts:
                    continue
                    
                last_checked_update_ts = current_ts

                cursor.execute("SELECT id, status, user_name, dept, issue, it_name, support_it_names, group_msg_id, it_id, it_msg_id, topic_id FROM tickets ORDER BY id DESC LIMIT 1000")
                rows = cursor.fetchall()
                current_db_keys = set()
                
                for row in rows:
                    t_id = row[0]
                    status = row[1]
                    user_name = row[2]
                    dept = row[3]
                    issue = row[4]
                    it_name = row[5]
                    support_it_names = row[6]
                    g_msg_id = row[7]
                    it_id_db = row[8]
                    it_msg_id_db = row[9]
                    topic_id_db = row[10]
                    
                    current_db_keys.add(t_id)
                    current_state = (status, user_name, dept, issue, it_name, support_it_names, it_id_db)
                    
                    if t_id not in bot_config.ticket_last_status:
                        bot_config.ticket_last_status[t_id] = current_state
                        continue
                        
                    old_state = bot_config.ticket_last_status[t_id]
                    old_status = old_state[0] if isinstance(old_state, tuple) else old_state
                    
                    if old_state != current_state:
                        status_changed = (old_status != status)
                        
                        if bot_config.bot and bot_config.GROUP_IT_ID:
                            if status == 'Hoàn thành':
                                if status_changed:
                                    if it_id_db and it_msg_id_db:
                                        try: bot_config.bot.edit_message_reply_markup(chat_id=it_id_db, message_id=it_msg_id_db, reply_markup=None)
                                        except: pass
                                    if g_msg_id:
                                        sup_text = f"\n👨‍🔧 **Hỗ trợ:** {support_it_names}" if support_it_names else ""
                                        text_fin = f"🚨 **YÊU CẦU #{t_id}**\n👤 Khách: {user_name}\n🏢 Phòng: {dept}\n📝 Lỗi: {truncate_text(issue, 3000)}\n\n✅ **Hoàn thành**\n👨‍💻 **IT Chính:** {it_name or 'N/A'}{sup_text}"
                                        safe_edit_message(bot_config.bot, bot_config.GROUP_IT_ID, g_msg_id, text_fin)
                                        try: bot_config.bot.unpin_chat_message(chat_id=bot_config.GROUP_IT_ID, message_id=g_msg_id)
                                        except: pass
                                    
                                    cursor.execute("SELECT user_id, role, topic_id FROM active_sessions WHERE ticket_id = ?", (t_id,))
                                    participants = cursor.fetchall()
                                    if participants:
                                        cursor.execute("DELETE FROM active_sessions WHERE ticket_id = ?", (t_id,))
                                        conn.commit()
                                        for p_id, role, p_topic in participants:
                                            try:
                                                if role in ['main', 'support']:
                                                    target_topic = p_topic if p_topic else (topic_id_db if role == 'main' else None)
                                                    if target_topic:
                                                        cursor.execute("SELECT workspace_group_id FROM it_staff WHERE it_id = ?", (p_id,))
                                                        ws_row = cursor.fetchone()
                                                        if ws_row and ws_row[0]:
                                                            try: bot_config.bot.edit_forum_topic(chat_id=ws_row[0], message_thread_id=target_topic, name=f"✅ [ĐÃ XONG] #{t_id} - {user_name}"[:120])
                                                            except: pass
                                                            try: bot_config.bot.send_message(ws_row[0], f"Ticket đã được đóng từ Web Dashboard.", message_thread_id=target_topic)
                                                            except: pass
                                                            try: bot_config.bot.close_forum_topic(chat_id=ws_row[0], message_thread_id=target_topic)
                                                            except: pass
                                                    else:
                                                        try: bot_config.bot.send_message(p_id, f"🎉 Ticket **#{t_id}** đã được đóng từ Web Dashboard.")
                                                        except: pass
                                                elif role == 'customer':
                                                    try: bot_config.bot.send_message(p_id, f"✅ **Sự cố của bạn đã hoàn tất.**\nVui lòng đánh giá dịch vụ:", reply_markup=get_rating_keyboard(t_id), parse_mode="Markdown")
                                                    except: pass
                                                    try: bot_config.bot.send_message(p_id, "👇 Báo sự cố khác:", reply_markup=get_report_keyboard())
                                                    except: pass
                                            except: pass
                                    else:
                                        if topic_id_db and it_id_db:
                                            cursor.execute("SELECT workspace_group_id FROM it_staff WHERE it_id = ?", (it_id_db,))
                                            ws_row = cursor.fetchone()
                                            if ws_row and ws_row[0]:
                                                try: bot_config.bot.edit_forum_topic(chat_id=ws_row[0], message_thread_id=topic_id_db, name=f"✅ [ĐÃ XONG] #{t_id} - {user_name}"[:120])
                                                except: pass
                                                try: bot_config.bot.send_message(ws_row[0], f"Ticket đã được đóng từ Web Dashboard.", message_thread_id=topic_id_db)
                                                except: pass
                                                try: bot_config.bot.close_forum_topic(chat_id=ws_row[0], message_thread_id=topic_id_db)
                                                except: pass
                                else:
                                    if g_msg_id:
                                        sup_text = f"\n👨‍🔧 **Hỗ trợ:** {support_it_names}" if support_it_names else ""
                                        text_fin = f"🚨 **YÊU CẦU #{t_id}**\n👤 Khách: {user_name}\n🏢 Phòng: {dept}\n📝 Lỗi: {truncate_text(issue, 3000)}\n\n✅ **Hoàn thành**\n👨‍💻 **IT Chính:** {it_name or 'N/A'}{sup_text}"
                                        safe_edit_message(bot_config.bot, bot_config.GROUP_IT_ID, g_msg_id, text_fin)

                            elif status == 'Đang xử lý':
                                if g_msg_id:
                                    sup_text = f"\n👨‍🔧 **Hỗ trợ:** {support_it_names}" if support_it_names else ""
                                    text_proc = f"🚨 **YÊU CẦU #{t_id}**\n👤 Khách: {user_name}\n🏢 Phòng: {dept}\n📝 Lỗi: {truncate_text(issue, 3000)}\n\n⏳ **Đang xử lý**\n👨‍💻 **IT Chính:** {it_name or 'N/A'}{sup_text}"
                                    markup_jump = None
                                    if topic_id_db and it_id_db: 
                                        cursor.execute("SELECT workspace_group_id FROM it_staff WHERE it_id = ?", (it_id_db,))
                                        ws_row = cursor.fetchone()
                                        if ws_row and ws_row[0] and str(ws_row[0]).startswith('-100'):
                                            clean_id = str(ws_row[0])[4:]
                                            topic_url = f"https://t.me/c/{clean_id}/{topic_id_db}"
                                            markup_jump = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(f"🚀 Đi tới Topic (Chỉ {it_name or 'IT'} vào được)", url=topic_url))
                                    
                                    safe_edit_message(bot_config.bot, bot_config.GROUP_IT_ID, g_msg_id, text_proc, reply_markup=markup_jump)

                            elif status == 'Mới':
                                if status_changed:
                                    if it_id_db and it_msg_id_db:
                                        try: bot_config.bot.edit_message_reply_markup(chat_id=it_id_db, message_id=it_msg_id_db, reply_markup=None)
                                        except: pass
                                    if g_msg_id:
                                        text_new = f"🚨 **YÊU CẦU #{t_id} (TRẢ LẠI / CHỜ NHẬN)**\n👤 Khách: {user_name}\n🏢 Phòng: {dept}\n📝 Lỗi: {truncate_text(issue, 3000)}"
                                        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤝 Nhận việc (Làm chính)", callback_data=f"claim_{t_id}"))
                                        safe_edit_message(bot_config.bot, bot_config.GROUP_IT_ID, g_msg_id, text_new, markup)
                                        try: bot_config.bot.pin_chat_message(chat_id=bot_config.GROUP_IT_ID, message_id=g_msg_id, disable_notification=True)
                                        except: pass
                                    
                                    cursor.execute("SELECT user_id, role, topic_id FROM active_sessions WHERE ticket_id = ?", (t_id,))
                                    participants = cursor.fetchall()
                                    if participants:
                                        cursor.execute("DELETE FROM active_sessions WHERE ticket_id = ?", (t_id,))
                                        conn.commit()
                                        for p_id, role, p_topic in participants:
                                            try:
                                                if role in ['main', 'support']:
                                                    target_topic = p_topic if p_topic else (topic_id_db if role == 'main' else None)
                                                    if target_topic:
                                                        cursor.execute("SELECT workspace_group_id FROM it_staff WHERE it_id = ?", (p_id,))
                                                        ws_row = cursor.fetchone()
                                                        if ws_row and ws_row[0]:
                                                            try: bot_config.bot.edit_forum_topic(chat_id=ws_row[0], message_thread_id=target_topic, name=f"❌ [TRẢ LẠI] #{t_id} - {user_name}"[:120])
                                                            except: pass
                                                            try: bot_config.bot.send_message(ws_row[0], f"Ticket đã bị Quản lý hủy từ Web.", message_thread_id=target_topic)
                                                            except: pass
                                                            try: bot_config.bot.close_forum_topic(chat_id=ws_row[0], message_thread_id=target_topic)
                                                            except: pass
                                                    else:
                                                        try: bot_config.bot.send_message(p_id, f"🔙 Ticket **#{t_id}** đã bị Quản lý hủy từ Web.")
                                                        except: pass
                                                elif role == 'customer':
                                                    try: bot_config.bot.send_message(p_id, "⚠️ IT đang bận, sự cố đã chuyển lại cho team!")
                                                    except: pass
                                            except: pass
                                    else:
                                        if topic_id_db and it_id_db:
                                            cursor.execute("SELECT workspace_group_id FROM it_staff WHERE it_id = ?", (it_id_db,))
                                            ws_row = cursor.fetchone()
                                            if ws_row and ws_row[0]:
                                                try: bot_config.bot.edit_forum_topic(chat_id=ws_row[0], message_thread_id=topic_id_db, name=f"❌ [TRẢ LẠI] #{t_id} - {user_name}"[:120])
                                                except: pass
                                                try: bot_config.bot.send_message(ws_row[0], f"Ticket bị hủy từ Web.", message_thread_id=topic_id_db)
                                                except: pass
                                                try: bot_config.bot.close_forum_topic(chat_id=ws_row[0], message_thread_id=topic_id_db)
                                                except: pass
                                else:
                                    if g_msg_id:
                                        text_new = f"🚨 **YÊU CẦU #{t_id} (ĐANG CHỜ TIẾP NHẬN)**\n👤 Khách: {user_name}\n🏢 Phòng: {dept}\n📝 Lỗi: {truncate_text(issue, 3000)}"
                                        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤝 Nhận việc (Làm chính)", callback_data=f"claim_{t_id}"))
                                        safe_edit_message(bot_config.bot, bot_config.GROUP_IT_ID, g_msg_id, text_new, markup)

                        bot_config.ticket_last_status[t_id] = current_state
            finally:
                conn.close()

            current_ids = list(bot_config.ticket_last_status.keys())
            for t_id in current_ids:
                if t_id not in current_db_keys:
                    bot_config.ticket_last_status.pop(t_id, None)
        except: pass

notified_tickets = set()

def auto_remind_it():
    while bot_config.is_running:
        try:
            time.sleep(60) 
            if not bot_config.bot or not bot_config.GROUP_IT_ID: continue
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
                    try: bot_config.bot.delete_message(bot_config.GROUP_IT_ID, bot_config.last_reminder_msg_id)
                    except: pass
                msg = bot_config.bot.send_message(bot_config.GROUP_IT_ID, f"📢 **THÔNG BÁO NHẮC VIỆC KHẨN CẤP!**\n\nCác sự cố {ids} đã treo hơn 15 phút. Anh em kiểm tra gấp! 🔥", parse_mode="Markdown")
                bot_config.last_reminder_msg_id = msg.message_id 
        except: pass

def run_bot_polling():
    while bot_config.is_running:
        try:
            if bot_config.bot: bot_config.bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
            time.sleep(2)  
        except:
            if bot_config.is_running: time.sleep(5)

def config_watchdog():
    while bot_config.is_running:
        try:
            new_token, new_group_str, new_offset = get_config_from_db()
            if not new_token or new_token == 'ĐIỀN TOKEN VÀO ĐÂY':
                time.sleep(10); continue
                
            try: new_group = int(new_group_str)
            except: time.sleep(10); continue

            bot_config.TIME_OFFSET = new_offset

            if new_token != bot_config.TOKEN:
                if bot_config.bot: bot_config.bot.stop_polling(); time.sleep(3) 
                bot_config.TOKEN = new_token
                bot_config.GROUP_IT_ID = new_group
                bot_config.bot = telebot.TeleBot(bot_config.TOKEN)
                setup_bot_handlers(bot_config.bot)
                sync_tickets_to_new_group(bot_config.bot, bot_config.GROUP_IT_ID)
                
            elif new_group != bot_config.GROUP_IT_ID:
                bot_config.GROUP_IT_ID = new_group
                if bot_config.bot:
                    sync_tickets_to_new_group(bot_config.bot, bot_config.GROUP_IT_ID)
        except: pass
        time.sleep(10) 

if __name__ == '__main__':
    print("🚀 Khởi động Hệ thống Bot IT (Giữ ghim Tracker & Xóa rác tự động)...")
    init_db()
    threading.Thread(target=config_watchdog, daemon=True).start()
    threading.Thread(target=auto_remind_it, daemon=True).start()
    threading.Thread(target=sync_hubs_with_db, daemon=True).start()
    run_bot_polling()