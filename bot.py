import threading
import time
import telebot
from telebot import types
from datetime import timedelta

import bot_config
from bot_db import init_db, connect_db, get_config_from_db
from bot_utils import get_adjusted_time, safe_edit_message, get_rating_keyboard, get_report_keyboard
from bot_handlers import setup_bot_handlers

def sync_tickets_to_new_group(current_bot, new_group_id):
    if not current_bot or not new_group_id: return
    conn = connect_db(); cursor = conn.cursor()
    row = cursor.execute("SELECT value FROM settings WHERE key='LAST_SYNCED_GROUP_ID'").fetchone()
    last_synced = row[0].strip() if row else None
    
    if str(new_group_id) == last_synced:
        conn.close(); return
        
    print(f"🔄 Phát hiện thay đổi Nhóm IT sang ID: {new_group_id}. Đang quét & bắn lại Ticket...")
    try: current_bot.send_message(new_group_id, "🔄 **HỆ THỐNG ĐANG ĐỒNG BỘ DỮ LIỆU...**", parse_mode="Markdown")
    except Exception as e:
        print(f"❌ Lỗi gửi thông báo (Kiểm tra lại xem Bot đã thêm vào nhóm chưa): {e}")
        conn.close(); return

    cursor.execute("SELECT id, status, user_name, dept, issue, it_name, support_it_names FROM tickets WHERE status != 'Hoàn thành' ORDER BY id ASC")
    active_tickets = cursor.fetchall()
    
    synced_count = 0
    for r in active_tickets:
        t_id, status, user_name, dept, issue, it_name, support_it_names = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
        try:
            if status == 'Mới':
                text_new = f"🚨 **YÊU CẦU #{t_id} (ĐANG CHỜ TIẾP NHẬN)**\n👤 Khách: {user_name}\n🏢 Phòng: {dept}\n📝 Lỗi: {issue}"
                markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤝 Nhận việc (Làm chính)", callback_data=f"claim_{t_id}"))
                sent_msg = current_bot.send_message(new_group_id, text_new, reply_markup=markup, parse_mode="Markdown")
                try: current_bot.pin_chat_message(chat_id=new_group_id, message_id=sent_msg.message_id, disable_notification=True)
                except: pass
                cursor.execute("UPDATE tickets SET group_msg_id = ? WHERE id = ?", (sent_msg.message_id, t_id))
                synced_count += 1
            elif status == 'Đang xử lý':
                sup_text = f"\n👨‍🔧 **Hỗ trợ:** {support_it_names}" if support_it_names else ""
                text_proc = f"🚨 **YÊU CẦU #{t_id}**\n👤 Khách: {user_name}\n🏢 Phòng: {dept}\n📝 Lỗi: {issue}\n\n⏳ **Đang xử lý**\n👨‍💻 **IT Chính:** {it_name or 'N/A'}{sup_text}"
                sent_msg = current_bot.send_message(new_group_id, text_proc, parse_mode="Markdown")
                try: current_bot.pin_chat_message(chat_id=new_group_id, message_id=sent_msg.message_id, disable_notification=True)
                except: pass
                cursor.execute("UPDATE tickets SET group_msg_id = ? WHERE id = ?", (sent_msg.message_id, t_id))
                synced_count += 1
        except Exception as ex: print(f"⚠️ Lỗi khi bắn Ticket #{t_id}: {ex}")

    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('LAST_SYNCED_GROUP_ID', ?)", (str(new_group_id),))
    conn.commit(); conn.close()
    try: current_bot.send_message(new_group_id, f"✅ **ĐỒNG BỘ HOÀN TẤT!**\nChuyển tiếp lại **{synced_count}** Ticket.", parse_mode="Markdown")
    except: pass

last_checked_update_ts = None

def sync_hubs_with_db():
    global last_checked_update_ts
    try:
        conn = connect_db(); cursor = conn.cursor()
        cursor.execute("SELECT id, status FROM tickets WHERE status != 'Hoàn thành'")
        for row in cursor.fetchall(): bot_config.ticket_last_status[row[0]] = row[1]
        
        row_ts = cursor.execute("SELECT value FROM settings WHERE key='LAST_TICKET_UPDATE'").fetchone()
        last_checked_update_ts = row_ts[0] if row_ts else None
        conn.close()
    except: pass
    
    while bot_config.is_running:
        try:
            time.sleep(3)
            conn = connect_db(); cursor = conn.cursor()
            
            # Kiểm tra mốc thời gian xem Web có thay đổi ticket nào không
            row_ts = cursor.execute("SELECT value FROM settings WHERE key='LAST_TICKET_UPDATE'").fetchone()
            current_ts = row_ts[0] if row_ts else None
            
            # Nếu thời gian không đổi và không có status nào cần retry thì bỏ qua truy vấn nặng
            if current_ts == last_checked_update_ts:
                conn.close()
                continue
                
            last_checked_update_ts = current_ts

            active_ids = [tid for tid, stat in bot_config.ticket_last_status.items() if stat != 'Hoàn thành']
            
            if active_ids:
                placeholders = ",".join("?" for _ in active_ids)
                query = f"SELECT id, status, user_name, dept, issue, it_name, support_it_names, group_msg_id, it_id, it_msg_id, topic_id FROM tickets WHERE status != 'Hoàn thành' OR id IN ({placeholders})"
                cursor.execute(query, active_ids)
            else:
                cursor.execute("SELECT id, status, user_name, dept, issue, it_name, support_it_names, group_msg_id, it_id, it_msg_id, topic_id FROM tickets WHERE status != 'Hoàn thành'")
                
            rows = cursor.fetchall()
            current_db_status = {}
            for row in rows:
                t_id, status = row[0], row[1]
                current_db_status[t_id] = status
                if t_id not in bot_config.ticket_last_status: bot_config.ticket_last_status[t_id] = status
                
                if bot_config.ticket_last_status[t_id] != status:
                    g_msg_id, it_id_db, it_msg_id_db, topic_id_db = row[7], row[8], row[9], row[10]
                    
                    if bot_config.bot and bot_config.GROUP_IT_ID:
                        if status == 'Hoàn thành':
                            if it_id_db and it_msg_id_db:
                                try: bot_config.bot.edit_message_reply_markup(chat_id=it_id_db, message_id=it_msg_id_db, reply_markup=None)
                                except: pass
                            if g_msg_id:
                                sup_text = f"\n👨‍🔧 **Hỗ trợ:** {row[6]}" if row[6] else ""
                                text_fin = f"🚨 **YÊU CẦU #{t_id}**\n👤 Khách: {row[2]}\n🏢 Phòng: {row[3]}\n📝 Lỗi: {row[4]}\n\n✅ **Hoàn thành**\n👨‍💻 **IT Chính:** {row[5] or 'N/A'}{sup_text}"
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
                                                    try: bot_config.bot.edit_forum_topic(chat_id=ws_row[0], message_thread_id=target_topic, name=f"✅ [ĐÃ XONG] #{t_id} - {row[2]}"[:120])
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
                                        try: bot_config.bot.edit_forum_topic(chat_id=ws_row[0], message_thread_id=topic_id_db, name=f"✅ [ĐÃ XONG] #{t_id} - {row[2]}"[:120])
                                        except: pass
                                        try: bot_config.bot.send_message(ws_row[0], f"Ticket đã được đóng từ Web Dashboard.", message_thread_id=topic_id_db)
                                        except: pass
                                        try: bot_config.bot.close_forum_topic(chat_id=ws_row[0], message_thread_id=topic_id_db)
                                        except: pass

                        elif status == 'Đang xử lý':
                            if g_msg_id:
                                text_proc = f"🚨 **YÊU CẦU #{t_id}**\n👤 Khách: {row[2]}\n🏢 Phòng: {row[3]}\n📝 Lỗi: {row[4]}\n\n⏳ **Đang xử lý**\n👨‍💻 **IT Chính:** {row[5] or 'N/A'}"
                                markup_jump = None
                                if row[10] and row[8]: 
                                    cursor.execute("SELECT workspace_group_id FROM it_staff WHERE it_id = ?", (row[8],))
                                    ws_row = cursor.fetchone()
                                    if ws_row and ws_row[0] and str(ws_row[0]).startswith('-100'):
                                        clean_id = str(ws_row[0])[4:]
                                        topic_url = f"https://t.me/c/{clean_id}/{row[10]}"
                                        markup_jump = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(f"🚀 Đi tới Topic (Chỉ {row[5]} vào được)", url=topic_url))
                                
                                safe_edit_message(bot_config.bot, bot_config.GROUP_IT_ID, g_msg_id, text_proc, reply_markup=markup_jump)
                            
                        elif status == 'Mới':
                            if it_id_db and it_msg_id_db:
                                try: bot_config.bot.edit_message_reply_markup(chat_id=it_id_db, message_id=it_msg_id_db, reply_markup=None)
                                except: pass
                            if g_msg_id:
                                text_new = f"🚨 **YÊU CẦU #{t_id} (TRẢ LẠI / CHỜ NHẬN)**\n👤 Khách: {row[2]}\n🏢 Phòng: {row[3]}\n📝 Lỗi: {row[4]}"
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
                                                    try: bot_config.bot.edit_forum_topic(chat_id=ws_row[0], message_thread_id=target_topic, name=f"❌ [TRẢ LẠI] #{t_id} - {row[2]}"[:120])
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
                                        try: bot_config.bot.edit_forum_topic(chat_id=ws_row[0], message_thread_id=topic_id_db, name=f"❌ [TRẢ LẠI] #{t_id} - {row[2]}"[:120])
                                        except: pass
                                        try: bot_config.bot.send_message(ws_row[0], f"Ticket bị hủy từ Web.", message_thread_id=topic_id_db)
                                        except: pass
                                        try: bot_config.bot.close_forum_topic(chat_id=ws_row[0], message_thread_id=topic_id_db)
                                        except: pass
                                        
                bot_config.ticket_last_status[t_id] = status
            conn.close()

            current_ids = list(bot_config.ticket_last_status.keys())
            for t_id in current_ids:
                if t_id not in current_db_status or current_db_status[t_id] == 'Hoàn thành':
                    bot_config.ticket_last_status.pop(t_id, None)
        except: pass

notified_tickets = set()

def auto_remind_it():
    while bot_config.is_running:
        try:
            time.sleep(60) 
            if not bot_config.bot or not bot_config.GROUP_IT_ID: continue
            conn = connect_db(); cursor = conn.cursor()
            fifteen_mins_ago = (get_adjusted_time() - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("SELECT id FROM tickets WHERE status = 'Mới' AND created_at < ?", (fifteen_mins_ago,))
            rows = cursor.fetchall(); conn.close()
            
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