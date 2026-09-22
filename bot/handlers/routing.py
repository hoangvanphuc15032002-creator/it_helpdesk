"""
Telegram Bot Routing & Message Dispatch Handler
Routes messages between Customers, IT Staff, and Forum Topics in Active Ticket Sessions, or manages user state machine.
"""
import time
from telebot import types
import config.settings as bot_config
from database.connection import connect_db
from database.repository import set_state, get_state, clear_state
from utils.helpers import get_adjusted_time, safe_send_content, send_ticket_to_group
from bot.keyboards import get_report_keyboard, get_departments_keyboard, get_departments_reply_keyboard, send_department_chunks

processed_msg_ids = set()
user_last_ticket_time = {}

ALL_CONTENT_TYPES = ['text', 'photo', 'document', 'video', 'audio', 'voice', 'sticker', 'animation', 'video_note', 'location', 'contact']

def register_routing_handlers(current_bot):

    @current_bot.message_handler(content_types=ALL_CONTENT_TYPES)
    def handle_all_messages(message):
        if message.chat.id == bot_config.GROUP_IT_ID: 
            try:
                member = current_bot.get_chat_member(message.chat.id, message.from_user.id)
                if member.status in ['creator', 'administrator']:
                    return  # Giữ lại tin nhắn của Admin / Chủ nhóm Telegram
            except Exception:
                pass

            try:
                current_bot.delete_message(message.chat.id, message.message_id)
            except Exception:
                pass
            return 
        
        # 1. Group / Supergroup messages (IT replying in Workspace Topic)
        if message.chat.type in ['group', 'supergroup']:
            if message.message_thread_id:
                conn = connect_db()
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT a.ticket_id, a.role, a.user_id 
                        FROM active_sessions a
                        JOIN it_staff i ON a.user_id = i.it_id
                        WHERE a.topic_id = ? AND i.workspace_group_id = ?
                    """, (message.message_thread_id, message.chat.id))
                    sess = cursor.fetchone()
                    
                    if not sess:
                        cursor.execute("SELECT id, it_id FROM tickets WHERE topic_id = ?", (message.message_thread_id,))
                        t_row = cursor.fetchone()
                        if t_row:
                            sess = (t_row[0], 'main', t_row[1])

                    if sess:
                        t_id, role, sender_uid = sess[0], sess[1], sess[2]
                        
                        cursor.execute('SELECT it_real_name FROM it_staff WHERE it_id = ?', (sender_uid,))
                        it_info = cursor.fetchone()
                        it_name = it_info[0] if it_info else "IT"
                        
                        prefix = f"👨‍💻 **IT {it_name}:** " if role == 'main' else f"👨‍🔧 **IT Hỗ trợ {it_name}:** "
                        
                        cursor.execute("SELECT user_id, role, topic_id FROM active_sessions WHERE ticket_id = ? AND user_id != ?", (t_id, sender_uid))
                        participants = cursor.fetchall()

                        if not participants:
                            cursor.execute("SELECT user_id FROM tickets WHERE id = ?", (t_id,))
                            cust_row = cursor.fetchone()
                            if cust_row and cust_row[0]:
                                participants = [(cust_row[0], 'customer', None)]
                        
                        photo_id = message.photo[-1].file_id if message.photo else None
                        doc_id = message.document.file_id if message.document else None
                        vid_id = message.video.file_id if message.video else None
                        voice_id = message.voice.file_id if message.voice else None
                        audio_id = message.audio.file_id if message.audio else None
                        sticker_id = message.sticker.file_id if message.sticker else None
                        anim_id = message.animation.file_id if message.animation else None
                        vnote_id = message.video_note.file_id if message.video_note else None
                        file_id = photo_id or doc_id or vid_id or voice_id or audio_id or sticker_id or anim_id or vnote_id
                        
                        for p_id, p_role, p_topic in participants:
                            target_chat = p_id
                            target_thread = None
                            
                            if p_role in ['main', 'support'] and p_topic:
                                cursor.execute("SELECT workspace_group_id FROM it_staff WHERE it_id = ?", (p_id,))
                                ws = cursor.fetchone()
                                if ws and ws[0]:
                                    target_chat = ws[0]
                                    target_thread = p_topic
                            
                            try:
                                safe_send_content(current_bot, target_chat, message.content_type, 
                                                  text_content=message.text, file_id=file_id, 
                                                  caption=message.caption, prefix=prefix, 
                                                  message_thread_id=target_thread)
                            except Exception:
                                pass
                finally:
                    conn.close()
            return
        
        # 2. Private chat messages
        if message.chat.type != 'private':
            return
        if message.text and message.text.startswith('/'):
            return
        sender_id = message.chat.id
        
        msg_key = (message.chat.id, message.message_id)
        if msg_key in processed_msg_ids:
            return
        processed_msg_ids.add(msg_key)
        if len(processed_msg_ids) > 2000:
            processed_msg_ids.clear()

        # Check Active Ticket Sessions FIRST before state machine!
        conn = connect_db()
        has_active_session = False
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT ticket_id, role FROM active_sessions WHERE user_id = ? ORDER BY ticket_id DESC", (sender_id,))
            active_sessions = cursor.fetchall()
            
            # Smart Fallback: if sender_id has a ticket in 'Đang xử lý'
            if not active_sessions:
                cursor.execute("SELECT id, user_id, it_id FROM tickets WHERE status = 'Đang xử lý' AND (user_id = ? OR it_id = ?) ORDER BY id DESC LIMIT 1", (sender_id, sender_id))
                t_row = cursor.fetchone()
                if t_row:
                    t_id, cust_id, it_id = t_row[0], t_row[1], t_row[2]
                    role = 'customer' if sender_id == cust_id else 'main'
                    active_sessions = [(t_id, role)]

            if active_sessions:
                has_active_session = True
                clear_state(sender_id)
                
                for active_session in active_sessions:
                    t_id, role = active_session[0], active_session[1]
                    prefix = "👤 **Khách:** " if role == 'customer' else ("👨‍💻 **IT Chính:** " if role == 'main' else "👨‍🔧 **IT Hỗ trợ:** ")

                    cursor.execute("SELECT user_id, role, topic_id FROM active_sessions WHERE ticket_id = ? AND user_id != ?", (t_id, sender_id))
                    participants = cursor.fetchall()
                    
                    # Smart Fallback: if participants missing IT or customer
                    if not participants:
                        cursor.execute("SELECT user_id, it_id, topic_id FROM tickets WHERE id = ?", (t_id,))
                        t_detail = cursor.fetchone()
                        if t_detail:
                            c_id, i_id, top_id = t_detail[0], t_detail[1], t_detail[2]
                            if role == 'customer' and i_id and i_id != sender_id:
                                participants = [(i_id, 'main', top_id)]
                            elif role in ['main', 'support'] and c_id and c_id != sender_id:
                                participants = [(c_id, 'customer', None)]

                    photo_id = message.photo[-1].file_id if message.photo else None
                    doc_id = message.document.file_id if message.document else None
                    vid_id = message.video.file_id if message.video else None
                    voice_id = message.voice.file_id if message.voice else None
                    audio_id = message.audio.file_id if message.audio else None
                    sticker_id = message.sticker.file_id if message.sticker else None
                    anim_id = message.animation.file_id if message.animation else None
                    vnote_id = message.video_note.file_id if message.video_note else None
                    file_id = photo_id or doc_id or vid_id or voice_id or audio_id or sticker_id or anim_id or vnote_id
                    
                    for p_id, p_role, p_topic in participants:
                        target_chat = p_id
                        target_thread = None
                        sent_ok = False
                        
                        if p_role in ['main', 'support'] and p_topic:
                            cursor.execute("SELECT workspace_group_id FROM it_staff WHERE it_id = ?", (p_id,))
                            ws = cursor.fetchone()
                            if ws and ws[0]:
                                target_chat = ws[0]
                                target_thread = p_topic
                        
                        # Primary attempt
                        try:
                            res = safe_send_content(current_bot, target_chat, message.content_type, 
                                              text_content=message.text, file_id=file_id, 
                                              caption=message.caption, prefix=prefix, 
                                              message_thread_id=target_thread)
                            if res: sent_ok = True
                        except Exception:
                            pass
                        
                        # Private Chat Fallback
                        if not sent_ok and target_thread:
                            try:
                                safe_send_content(current_bot, p_id, message.content_type, 
                                                  text_content=message.text, file_id=file_id, 
                                                  caption=message.caption, prefix=prefix, 
                                                  message_thread_id=None)
                            except Exception:
                                pass
                return
        finally:
            conn.close()

        if has_active_session:
            return

        # 3. State machine handling for non-active users (Onboarding / Reporting)
        step, temp_data = get_state(sender_id)
        
        if step:
            if step == 'waiting_for_it_name':
                set_state(sender_id, 'waiting_for_it_phone', message.text)
                current_bot.send_message(sender_id, f"📱 Chào **{message.text}**, nhập hoặc chia sẻ **Số điện thoại** của bạn:", parse_mode="Markdown")
                return
            elif step == 'waiting_for_it_phone':
                phone_text = message.text
                if message.content_type == 'contact' and message.contact:
                    phone_text = message.contact.phone_number
                it_name, it_phone = temp_data, phone_text
                if not it_phone:
                    current_bot.send_message(sender_id, "⚠️ **Vui lòng nhập hoặc chia sẻ Số điện thoại của bạn!**")
                    return
                conn = connect_db()
                try:
                    conn.execute('INSERT OR REPLACE INTO it_staff (it_id, it_real_name, it_phone) VALUES (?, ?, ?)', (sender_id, it_name, it_phone))
                    conn.commit()
                finally:
                    conn.close()
                clear_state(sender_id)
                current_bot.send_message(sender_id, f"✅ Xác thực thành công!\n👤 {it_name} - 📞 {it_phone}")
                return
            elif step == 'ask_name':
                if message.content_type != 'text' or not message.text or len(message.text.strip()) < 2:
                    current_bot.send_message(sender_id, "⚠️ **Vui lòng nhập đúng Họ và Tên của bạn bằng văn bản!**")
                    return
                
                user_name = message.text.strip()
                set_state(sender_id, 'ask_dept', user_name)
                
                conn = connect_db()
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, name FROM departments ORDER BY name ASC")
                    depts = cursor.fetchall()
                    send_department_chunks(current_bot, sender_id, user_name, depts, chunk_size=15)
                finally:
                    conn.close()
                return
            elif step == 'ask_dept':
                dept_text = message.text.strip() if (message.text and message.content_type == 'text') else "Khác"
                
                conn = connect_db()
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM departments WHERE LOWER(name) LIKE ?", (f"%{dept_text.lower()}%",))
                    matched = cursor.fetchone()
                    dept_name = matched[0] if matched else dept_text
                    
                    user_name = temp_data if (temp_data and temp_data != 'None') else (message.from_user.full_name or f"Khách #{sender_id}")
                    cursor.execute('INSERT OR REPLACE INTO users (user_id, name, dept) VALUES (?, ?, ?)', (sender_id, user_name, dept_name))
                    conn.commit()
                finally:
                    conn.close()
                clear_state(sender_id)
                try:
                    current_bot.send_message(sender_id, f"✅ Đã lưu thông tin!\n👤 Tên: **{user_name}**\n🏢 Phòng: **{dept_name}**", reply_markup=get_report_keyboard(), parse_mode="Markdown")
                except Exception:
                    current_bot.send_message(sender_id, f"✅ Đã lưu thông tin!\n👤 Tên: {user_name}\n🏢 Phòng: {dept_name}", reply_markup=get_report_keyboard())
                return

        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT it_real_name FROM it_staff WHERE it_id = ?', (sender_id,))
            is_it = cursor.fetchone()
            if is_it:
                current_bot.send_message(sender_id, f"👨‍💻 Chào IT **{is_it[0]}**. Bạn hiện không xử lý sự cố nào trong chat riêng.\n*(💡 Nếu bạn đang bật chế độ Workspace, hãy vào Nhóm làm việc riêng của bạn và chọn đúng Topic của Ticket để chat với khách nhé!)*", parse_mode="Markdown")
                return

            cursor.execute('SELECT name, dept FROM users WHERE user_id = ?', (sender_id,))
            user = cursor.fetchone()
        finally:
            conn.close()

        if not user:
            set_state(sender_id, 'ask_name')
            current_bot.send_message(sender_id, "👋 Chào mừng bạn! Cho biết **Họ và Tên** của bạn:")
            return

        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM tickets WHERE user_id = ? AND status = 'Mới'", (sender_id,))
            pending_ticket = cursor.fetchone()
            if pending_ticket:
                current_bot.send_message(sender_id, f"⏳ Sự cố **#{pending_ticket[0]}** đang chờ tiếp nhận. Vui lòng không gửi thêm!", parse_mode="Markdown")
                return
                
            if step != 'waiting_for_issue':
                current_bot.send_message(sender_id, "⚠️ **Vui lòng nhấn nút '🚨 Báo sự cố mới' bên dưới trước khi mô tả lỗi!**", reply_markup=get_report_keyboard(), parse_mode="Markdown")
                return
                
            now = time.time()
            if sender_id in user_last_ticket_time and now - user_last_ticket_time[sender_id] < 3:
                return
            user_last_ticket_time[sender_id] = now
                
            clear_state(sender_id)

            if temp_data:
                try:
                    current_bot.edit_message_reply_markup(chat_id=sender_id, message_id=int(temp_data), reply_markup=None)
                except Exception:
                    pass

            issue_text = message.text or message.caption or "Gửi đính kèm"
            cursor.execute('INSERT INTO tickets (user_id, user_name, dept, issue, status, created_at) VALUES (?, ?, ?, ?, ?, ?)', (sender_id, user[0], user[1], issue_text, 'Mới', get_adjusted_time().strftime("%Y-%m-%d %H:%M:%S")))
            ticket_id = cursor.lastrowid
            conn.commit()
            
            current_bot.send_message(sender_id, "✅ **Đã gửi IT.** Vui lòng đợi.", parse_mode="Markdown")
            msg_to_it = f"🚨 **YÊU CẦU MỚI!**\n🆔 Mã: #{ticket_id}\n👤 Khách: {user[0]}\n🏢 Phòng: {user[1]}\n📝 Nội dung: {issue_text}"
            markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤝 Nhận việc (Làm chính)", callback_data=f"claim_{ticket_id}"))
            
            photo_id = message.photo[-1].file_id if message.photo else None
            doc_id = message.document.file_id if message.document else None
            vid_id = message.video.file_id if message.video else None
            voice_id = message.voice.file_id if message.voice else None
            audio_id = message.audio.file_id if message.audio else None
            file_id = photo_id or doc_id or vid_id or voice_id or audio_id
            
            sent_msg = send_ticket_to_group(current_bot, bot_config.GROUP_IT_ID, message.content_type, file_id, msg_to_it, reply_markup=markup)

            if sent_msg:
                try:
                    current_bot.pin_chat_message(chat_id=bot_config.GROUP_IT_ID, message_id=sent_msg.message_id, disable_notification=True)
                except Exception:
                    pass
                cursor.execute("UPDATE tickets SET group_msg_id = ? WHERE id = ?", (sent_msg.message_id, ticket_id))
                conn.commit()
                bot_config.ticket_last_status[ticket_id] = 'Mới'
        finally:
            conn.close()
