import telebot
from telebot import types
import sqlite3
import time

import bot_config
from bot_db import connect_db, set_state, get_state, clear_state
from bot_utils import get_adjusted_time, get_rating_keyboard, get_report_keyboard, safe_edit_message, safe_send_content

processed_msg_ids = set()
user_last_ticket_time = {}

def setup_bot_handlers(current_bot):

    @current_bot.message_handler(commands=['setworkspace'])
    def set_workspace_group(message):
        if message.chat.type not in ['group', 'supergroup']:
            current_bot.reply_to(message, "❌ Lệnh này phải được gõ trong Nhóm Workspace làm việc riêng của bạn!")
            return
        user_id = message.from_user.id
        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT it_real_name FROM it_staff WHERE it_id = ?", (user_id,))
            it = cursor.fetchone()
            if not it:
                current_bot.reply_to(message, "❌ Bạn chưa xác thực tài khoản IT! Hãy gõ /start ở chat riêng với Bot để đăng ký trước.")
                return
            
            cursor.execute("UPDATE it_staff SET workspace_group_id = ? WHERE it_id = ?", (message.chat.id, user_id))
            conn.commit()
        finally:
            conn.close()

        text = (
            f"✅ **ĐÃ KẾT NỐI WORKSPACE THÀNH CÔNG!**\n\n"
            f"👨‍💻 IT: **{it[0]}**\n"
            f"🏢 Nhóm này sẽ là văn phòng làm việc riêng của bạn.\n"
            f"👉 Từ nay bạn có thể nhận **không giới hạn Ticket cùng lúc**. Mỗi Ticket khi nhận sẽ tự động tạo thành 1 Topic tại đây!"
        )
        current_bot.reply_to(message, text, parse_mode="Markdown")

    @current_bot.message_handler(commands=['giaicuu'])
    def rescue_command(message):
        if message.chat.type != 'private': return
        user_id = message.from_user.id
        
        conn = connect_db()
        try:
            cursor = conn.cursor()
            
            cursor.execute('SELECT it_real_name FROM it_staff WHERE it_id = ?', (user_id,))
            is_it = cursor.fetchone()
            
            cursor.execute("DELETE FROM active_sessions WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM user_states_db WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM active_sessions WHERE ticket_id NOT IN (SELECT id FROM tickets WHERE status != 'Hoàn thành')")
            
            conn.commit()
        finally:
            conn.close()
        
        if is_it:
            text = (
                "🚑 **GIẢI CỨU THÀNH CÔNG!**\n\n"
                "✅ Tài khoản IT của bạn đã được reset.\n"
                "👉 Bạn đã được trả về trạng thái tự do và có thể nhận việc mới!"
            )
            current_bot.reply_to(message, text, parse_mode="Markdown")
        else:
            text = (
                "🚑 **GIẢI CỨU THÀNH CÔNG!**\n\n"
                "✅ Kết nối của bạn đã được làm mới.\n"
                "👉 Vui lòng sử dụng các nút bên dưới để tiếp tục!"
            )
            current_bot.reply_to(message, text, reply_markup=get_report_keyboard(), parse_mode="Markdown")

    @current_bot.message_handler(commands=['getid'])
    def get_exact_id(message):
        current_bot.send_message(message.chat.id, f"🎯 ID CHÍNH XÁC CỦA NHÓM NÀY LÀ:\n\n`{message.chat.id}`\n\n👉 Copy DÃY SỐ TRÊN dán vào Web!", parse_mode="Markdown")

    @current_bot.message_handler(commands=['pending'])
    def check_pending(message):
        if message.chat.id != bot_config.GROUP_IT_ID: return 
        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, user_name, dept, created_at FROM tickets WHERE status = 'Mới'")
            rows = cursor.fetchall()
        finally:
            conn.close()

        if not rows: current_bot.send_message(bot_config.GROUP_IT_ID, "✅ Không còn sự cố nào đang chờ tiếp nhận.")
        else:
            text = "⚠️ **DANH SÁCH SỰ CỐ ĐANG CHỜ:**\n\n"
            for r in rows: text += f"🔹 **#{r[0]}** - {r[1]} - {r[2]} - *{r[3][11:16]}*\n"
            current_bot.send_message(bot_config.GROUP_IT_ID, text, parse_mode="Markdown")

    @current_bot.message_handler(content_types=['new_chat_members'])
    def welcome_new_it_member(message):
        if message.chat.id != bot_config.GROUP_IT_ID: return
        auth_url = f"https://t.me/{current_bot.get_me().username}?start=iam_it"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("👨‍💻 Bấm vào đây để Xác Thực IT", url=auth_url))
        for new_member in message.new_chat_members:
            if not new_member.is_bot: 
                user_name = new_member.first_name + (f" {new_member.last_name}" if new_member.last_name else "")
                text = f"👋 Chào mừng đồng đội mới [{user_name}](tg://user?id={new_member.id})!\n\n🚨 Hãy nhấn nút bên dưới và bấm **Start** xác thực."
                current_bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

    @current_bot.message_handler(commands=['setup_it'])
    def setup_it_group(message):
        if message.chat.id != bot_config.GROUP_IT_ID: return
        auth_url = f"https://t.me/{current_bot.get_me().username}?start=iam_it"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("👨‍💻 Xác Thực IT", url=auth_url))
        current_bot.send_message(message.chat.id, "🚨 **NHÂN SỰ IT:** Bấm nút để đăng ký tên & SĐT.", reply_markup=markup, parse_mode="Markdown")

    @current_bot.message_handler(commands=['setup'])
    def setup_group(message):
        if message.chat.type == 'private': return
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🆘 Liên hệ IT (Báo sự cố)", url=f"https://t.me/{current_bot.get_me().username}"))
        current_bot.send_message(message.chat.id, f"🏢 **CỔNG TIẾP NHẬN SỰ CỐ IT CHUNG**\n\nNhấn nút bên dưới để báo lỗi nhé.", reply_markup=markup, parse_mode="Markdown")

    @current_bot.message_handler(commands=['start'])
    def start(message):
        if message.chat.type != 'private': return
        args = message.text.split()
        conn = connect_db()
        try:
            cursor = conn.cursor()
            if len(args) > 1:
                if args[1] == 'it_support': return
                if args[1] == 'iam_it': 
                    set_state(message.from_user.id, 'waiting_for_it_name')
                    current_bot.send_message(message.chat.id, "👨‍💻 **XÁC THỰC IT:** Nhập **Họ tên hiển thị** của bạn:", parse_mode="Markdown")
                    return
                try:
                    dept = bytes.fromhex(args[1]).decode('utf-8')
                    cursor.execute('INSERT OR REPLACE INTO users (user_id, name, dept) VALUES (?, ?, ?)', (message.from_user.id, message.from_user.full_name, dept))
                    conn.commit()
                    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Hủy báo cáo", callback_data="cancelReport"))
                    msg = current_bot.send_message(message.chat.id, f"✅ **Hệ thống IT - {dept}** chào bạn!\n\nMời bạn mô tả lỗi tại đây.", reply_markup=markup, parse_mode="Markdown")
                    set_state(message.from_user.id, 'waiting_for_issue', str(msg.message_id))
                except: pass
            else:
                cursor.execute('SELECT it_real_name FROM it_staff WHERE it_id = ?', (message.from_user.id,))
                if cursor.fetchone():
                    current_bot.send_message(message.chat.id, "👨‍💻 Chào IT. Tài khoản đã xác thực.\nHãy theo dõi nhóm tổng để nhận việc nhé!\n\n*(💡 Mẹo: Tạo nhóm mới, thêm Bot làm Admin và gõ /setworkspace để làm việc đa nhiệm bằng Forum Topic)*", parse_mode="Markdown")
                else:
                    cursor.execute('SELECT name, dept FROM users WHERE user_id = ?', (message.from_user.id,))
                    user = cursor.fetchone()
                    if user: 
                        current_bot.send_message(message.chat.id, f"👋 Chào **{user[0]}** - Phòng: **{user[1]}**.", reply_markup=get_report_keyboard(), parse_mode="Markdown")
                    else:
                        set_state(message.from_user.id, 'ask_name')
                        current_bot.send_message(message.chat.id, "👋 Chào mừng bạn! Cho biết **Họ và Tên** của bạn:")
        finally:
            conn.close()

    @current_bot.message_handler(content_types=['pinned_message'])
    def delete_pin_system_message(message):
        try: current_bot.delete_message(message.chat.id, message.message_id)
        except: pass

    @current_bot.message_handler(content_types=['text', 'photo', 'document', 'video', 'audio', 'voice'])
    def handle_all_messages(message):
        if message.chat.id == bot_config.GROUP_IT_ID: 
            try: current_bot.delete_message(message.chat.id, message.message_id)
            except: pass
            return 
        
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
                    if sess:
                        t_id, role, sender_uid = sess[0], sess[1], sess[2]
                        
                        cursor.execute('SELECT it_real_name FROM it_staff WHERE it_id = ?', (sender_uid,))
                        it_info = cursor.fetchone()
                        it_name = it_info[0] if it_info else "IT"
                        
                        prefix = f"👨‍💻 **IT {it_name}:** " if role == 'main' else f"👨‍🔧 **IT Hỗ trợ {it_name}:** "
                        
                        cursor.execute("SELECT user_id, role, topic_id FROM active_sessions WHERE ticket_id = ? AND user_id != ?", (t_id, sender_uid))
                        for p_id, p_role, p_topic in cursor.fetchall():
                            target_chat = p_id
                            target_thread = None
                            
                            if p_role in ['main', 'support'] and p_topic:
                                cursor.execute("SELECT workspace_group_id FROM it_staff WHERE it_id = ?", (p_id,))
                                ws = cursor.fetchone()
                                if ws and ws[0]:
                                    target_chat = ws[0]
                                    target_thread = p_topic
                            
                            try:
                                photo_id = message.photo[-1].file_id if message.photo else None
                                doc_id = message.document.file_id if message.document else None
                                vid_id = message.video.file_id if message.video else None
                                voice_id = message.voice.file_id if message.voice else None
                                audio_id = message.audio.file_id if message.audio else None
                                file_id = photo_id or doc_id or vid_id or voice_id or audio_id
                                
                                safe_send_content(current_bot, target_chat, message.content_type, 
                                                  text_content=message.text, file_id=file_id, 
                                                  caption=message.caption, prefix=prefix, 
                                                  message_thread_id=target_thread)
                            except: pass
                finally:
                    conn.close()
            return
        
        if message.chat.type != 'private': return
        if message.text and message.text.startswith('/'): return
        sender_id = message.chat.id
        
        # Chống Telegram retry trùng message_id
        msg_key = (message.chat.id, message.message_id)
        if msg_key in processed_msg_ids:
            return
        processed_msg_ids.add(msg_key)
        if len(processed_msg_ids) > 2000:
            processed_msg_ids.clear()

        step, temp_data = get_state(sender_id)
        
        if step:
            if step == 'waiting_for_it_name':
                set_state(sender_id, 'waiting_for_it_phone', message.text)
                current_bot.send_message(sender_id, f"📱 Chào **{message.text}**, nhập **Số điện thoại** của bạn:", parse_mode="Markdown")
                return
            elif step == 'waiting_for_it_phone':
                it_name, it_phone = temp_data, message.text
                conn = connect_db()
                try:
                    conn.execute('INSERT OR REPLACE INTO it_staff (it_id, it_real_name, it_phone) VALUES (?, ?, ?)', (sender_id, it_name, it_phone))
                    conn.commit()
                finally:
                    conn.close()
                clear_state(sender_id)
                current_bot.send_message(sender_id, f"✅ Xác thực thành công!\n👤 {it_name} - 📞 {it_phone}")
                return

        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT ticket_id, role FROM active_sessions WHERE user_id = ? ORDER BY ticket_id DESC", (sender_id,))
            active_sessions = cursor.fetchall()
            
            if active_sessions:
                for active_session in active_sessions:
                    t_id, role = active_session[0], active_session[1]
                    if role == 'customer': prefix = "👤 **Khách:** "
                    elif role == 'main': prefix = "👨‍💻 **IT Chính:** "
                    else: prefix = "👨‍🔧 **IT Hỗ trợ:** "

                    cursor.execute("SELECT user_id, role, topic_id FROM active_sessions WHERE ticket_id = ? AND user_id != ?", (t_id, sender_id))
                    for p_id, p_role, p_topic in cursor.fetchall():
                        target_chat = p_id
                        target_thread = None
                        
                        if p_role in ['main', 'support'] and p_topic:
                            cursor.execute("SELECT workspace_group_id FROM it_staff WHERE it_id = ?", (p_id,))
                            ws = cursor.fetchone()
                            if ws and ws[0]:
                                target_chat = ws[0]
                                target_thread = p_topic
                        
                        try:
                            photo_id = message.photo[-1].file_id if message.photo else None
                            doc_id = message.document.file_id if message.document else None
                            vid_id = message.video.file_id if message.video else None
                            voice_id = message.voice.file_id if message.voice else None
                            audio_id = message.audio.file_id if message.audio else None
                            file_id = photo_id or doc_id or vid_id or voice_id or audio_id
                            
                            safe_send_content(current_bot, target_chat, message.content_type, 
                                              text_content=message.text, file_id=file_id, 
                                              caption=message.caption, prefix=prefix, 
                                              message_thread_id=target_thread)
                        except: pass
                return
        finally:
            conn.close()

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
            conn = connect_db()
            try:
                cursor = conn.cursor()
                if not step:
                    set_state(sender_id, 'ask_name')
                    current_bot.send_message(sender_id, "👋 Chào mừng bạn! Cho biết **Họ và Tên** của bạn:")
                elif step == 'ask_name':
                    if message.content_type != 'text' or not message.text or len(message.text.strip()) < 2:
                        current_bot.send_message(sender_id, "⚠️ **Vui lòng nhập đúng Họ và Tên của bạn bằng văn bản!**")
                        return
                    
                    user_name = message.text.strip()
                    set_state(sender_id, 'ask_dept', user_name)
                    
                    cursor.execute("SELECT id, name FROM departments ORDER BY name ASC")
                    depts = cursor.fetchall()
                    if depts:
                        markup = types.InlineKeyboardMarkup(row_width=1) 
                        for d_id, d_name in depts: markup.add(types.InlineKeyboardButton(d_name, callback_data=f"seldept_{d_id}"))
                        current_bot.send_message(sender_id, f"Chào **{user_name}**! Vui lòng chọn **Phòng ban** của bạn bên dưới:", reply_markup=markup, parse_mode="Markdown")
                    else:
                        current_bot.send_message(sender_id, f"Chào **{user_name}**! 🏢 Nhập tên **Phòng ban** của bạn:")
                elif step == 'ask_dept':
                    cursor.execute("SELECT id, name FROM departments ORDER BY name ASC")
                    depts = cursor.fetchall()
                    if depts:
                        markup = types.InlineKeyboardMarkup(row_width=1) 
                        for d_id, d_name in depts: markup.add(types.InlineKeyboardButton(d_name, callback_data=f"seldept_{d_id}"))
                        current_bot.send_message(sender_id, "⚠️ **VUI LÒNG CHỌN PHÒNG BAN!**\n\n👉 Bạn hãy nhấn vào một trong các nút chọn **Phòng ban** bên dưới. Không tự gõ văn bản ở bước này!", reply_markup=markup, parse_mode="Markdown")
                    else:
                        dept_text = message.text.strip() if message.text else "Khác"
                        user_name = temp_data if (temp_data and temp_data != 'None') else (message.from_user.full_name or f"Khách #{sender_id}")
                        cursor.execute('INSERT INTO users (user_id, name, dept) VALUES (?, ?, ?)', (sender_id, user_name, dept_text))
                        conn.commit()
                        clear_state(sender_id)
                        current_bot.send_message(sender_id, f"✅ Đã lưu thông tin!\n👤 Tên: **{user_name}**\n🏢 Phòng: **{dept_text}**", reply_markup=get_report_keyboard(), parse_mode="Markdown")
            finally:
                conn.close()
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
                try: current_bot.edit_message_reply_markup(chat_id=sender_id, message_id=int(temp_data), reply_markup=None)
                except: pass

            issue_text = message.text or message.caption or "Gửi đính kèm"
            cursor.execute('INSERT INTO tickets (user_id, user_name, dept, issue, status, created_at) VALUES (?, ?, ?, ?, ?, ?)', (sender_id, user[0], user[1], issue_text, 'Mới', get_adjusted_time().strftime("%Y-%m-%d %H:%M:%S")))
            ticket_id = cursor.lastrowid
            conn.commit()
            
            current_bot.send_message(sender_id, "✅ **Đã gửi IT.** Vui lòng đợi.", parse_mode="Markdown")
            msg_to_it = f"🚨 **YÊU CẦU MỚI!**\n🆔 Mã: #{ticket_id}\n👤 Khách: {user[0]}\n🏢 Phòng: {user[1]}\n📝 Nội dung: {issue_text}"
            markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤝 Nhận việc (Làm chính)", callback_data=f"claim_{ticket_id}"))
            
            sent_msg = None
            if message.content_type == 'photo': sent_msg = current_bot.send_photo(bot_config.GROUP_IT_ID, message.photo[-1].file_id, caption=msg_to_it, reply_markup=markup, parse_mode="Markdown")
            elif message.content_type == 'video': sent_msg = current_bot.send_video(bot_config.GROUP_IT_ID, message.video.file_id, caption=msg_to_it, reply_markup=markup, parse_mode="Markdown")
            elif message.content_type == 'document': sent_msg = current_bot.send_document(bot_config.GROUP_IT_ID, message.document.file_id, caption=msg_to_it, reply_markup=markup, parse_mode="Markdown")
            elif message.content_type == 'voice': sent_msg = current_bot.send_voice(bot_config.GROUP_IT_ID, message.voice.file_id, caption=msg_to_it, reply_markup=markup, parse_mode="Markdown")
            elif message.content_type == 'audio': sent_msg = current_bot.send_audio(bot_config.GROUP_IT_ID, message.audio.file_id, caption=msg_to_it, reply_markup=markup, parse_mode="Markdown")
            else: sent_msg = current_bot.send_message(bot_config.GROUP_IT_ID, msg_to_it, reply_markup=markup, parse_mode="Markdown")

            if sent_msg:
                try: current_bot.pin_chat_message(chat_id=bot_config.GROUP_IT_ID, message_id=sent_msg.message_id, disable_notification=True)
                except: pass
                cursor.execute("UPDATE tickets SET group_msg_id = ? WHERE id = ?", (sent_msg.message_id, ticket_id))
                conn.commit()
                bot_config.ticket_last_status[ticket_id] = 'Mới'
        finally:
            conn.close()

    @current_bot.callback_query_handler(func=lambda call: True)
    def callback_handler(call):
        if call.data == 'reportIssue':
            markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Hủy báo cáo", callback_data="cancelReport"))
            try: 
                current_bot.edit_message_text("📝 **Mời bạn mô tả lỗi:**\n*(Hoặc nhấn nút Hủy)*", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")
                set_state(call.from_user.id, 'waiting_for_issue', str(call.message.message_id))
            except: 
                set_state(call.from_user.id, 'waiting_for_issue')
            return

        if call.data == 'cancelReport':
            clear_state(call.from_user.id)
            try: current_bot.edit_message_text("✅ Đã hủy.", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_report_keyboard())
            except: pass
            return

        if call.data == 'changeDept':
            conn = connect_db(); cursor = conn.cursor()
            cursor.execute('SELECT name FROM users WHERE user_id = ?', (call.from_user.id,))
            user = cursor.fetchone()
            if user:
                set_state(call.from_user.id, 'ask_dept', user[0])
                
                cursor.execute("SELECT id, name FROM departments ORDER BY name ASC")
                depts = cursor.fetchall()
                if depts:
                    markup = types.InlineKeyboardMarkup(row_width=1) 
                    for d_id, d_name in depts: markup.add(types.InlineKeyboardButton(d_name, callback_data=f"seldept_{d_id}"))
                    current_bot.edit_message_text(f"🔄 Đang cập nhật cho **{user[0]}**\nMời bạn chọn **Phòng ban** mới:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")
                else:
                    current_bot.edit_message_text("🏢 Vui lòng nhập tên **Phòng ban** mới của bạn:", chat_id=call.message.chat.id, message_id=call.message.message_id)
            conn.close(); return

        if call.data.startswith('seldept_'):
            dept_id = call.data[8:]
            sender_id = call.from_user.id
            step, temp_data = get_state(sender_id)
            if step == 'ask_dept':
                conn = connect_db(); cursor = conn.cursor()
                cursor.execute("SELECT name FROM departments WHERE id = ?", (dept_id,))
                d_row = cursor.fetchone()
                if d_row:
                    dept_name = d_row[0]
                    user_name = temp_data if (temp_data and temp_data != 'None') else (call.from_user.full_name or f"Khách #{sender_id}")
                    cursor.execute('INSERT OR REPLACE INTO users (user_id, name, dept) VALUES (?, ?, ?)', (sender_id, user_name, dept_name))
                    conn.commit()
                    clear_state(sender_id)
                    current_bot.edit_message_text(f"✅ Đã lưu thông tin!\n👤 Tên: **{user_name}**\n🏢 Phòng ban: **{dept_name}**", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_report_keyboard(), parse_mode="Markdown")
                conn.close()
            return

        parts = call.data.split('_')
        action, ticket_id = parts[0], parts[1]
        it_id = call.from_user.id

        if action == 'rate':
            conn = connect_db(); cursor = conn.cursor(); cursor.execute('UPDATE tickets SET rating = ? WHERE id = ?', (parts[2], ticket_id)); conn.commit(); conn.close()
            current_bot.edit_message_text(f"⭐ Đã đánh giá {parts[2]} sao!", chat_id=call.message.chat.id, message_id=call.message.message_id); return

        conn = connect_db(); cursor = conn.cursor()
        cursor.execute('SELECT it_real_name, it_phone, workspace_group_id FROM it_staff WHERE it_id = ?', (it_id,))
        it_info = cursor.fetchone()
        if not it_info and action in ['claim', 'join', 'leave']:
            current_bot.answer_callback_query(call.id, "❌ Chưa xác thực IT!", show_alert=True); conn.close(); return

        if action == 'claim':
            workspace_id = it_info[2] if it_info and len(it_info) > 2 and it_info[2] else None
            
            if not workspace_id:
                cursor.execute("SELECT ticket_id FROM active_sessions WHERE user_id = ?", (it_id,))
                if cursor.fetchone():
                    current_bot.answer_callback_query(call.id, "❌ BẠN ĐANG BẬN! Hãy tạo Nhóm Workspace riêng và gõ /setworkspace để nhận nhiều Ticket cùng lúc!", show_alert=True)
                    conn.close(); return

            cursor.execute("UPDATE tickets SET it_id = ?, it_name = ?, status = 'Đang xử lý' WHERE id = ? AND status = 'Mới'", (it_id, it_info[0], ticket_id))
            if cursor.rowcount == 0:
                current_bot.answer_callback_query(call.id, "❌ Chậm tay! Đã có người nhận hoặc Ticket bị hủy.", show_alert=True); conn.close(); return
            
            cursor.execute('SELECT user_id, user_name, dept, issue FROM tickets WHERE id = ?', (ticket_id,))
            res = cursor.fetchone()
            user_id = res[0]
            
            topic_id = None
            topic_url = None
            sent_it_msg = None
            
            if workspace_id:
                try:
                    topic_name = f"🚨 #{ticket_id} - {res[1]} ({res[2]})"[:120]
                    topic = current_bot.create_forum_topic(chat_id=workspace_id, name=topic_name)
                    topic_id = topic.message_thread_id
                    
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("✅ Hoàn thành", callback_data=f"done_{ticket_id}_{call.message.message_id}"),
                               types.InlineKeyboardButton("🆘 Thêm người hỗ trợ", callback_data=f"asksupport_{ticket_id}_{call.message.message_id}"))
                    markup.add(types.InlineKeyboardButton("🔙 Trả lại (Hủy nhận)", callback_data=f"abort_{ticket_id}_{call.message.message_id}"))
                    
                    msg_to_it = f"🚀 **[LÀM CHÍNH] YÊU CẦU #{ticket_id}**\n👤 Khách: {res[1]}\n🏢 Phòng: {res[2]}\n📝 Lỗi: {res[3]}\n👉 Chat trực tiếp với khách bên dưới:"
                    sent_it_msg = current_bot.send_message(workspace_id, msg_to_it, reply_markup=markup, parse_mode="Markdown", message_thread_id=topic_id)
                    
                    if str(workspace_id).startswith('-100'):
                        clean_id = str(workspace_id)[4:]
                        topic_url = f"https://t.me/c/{clean_id}/{topic_id}"
                        
                except Exception as e:
                    print(f"⚠️ Lỗi tạo Topic: {e}")
                    workspace_id = None
            
            if not workspace_id:
                try:
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("✅ Hoàn thành", callback_data=f"done_{ticket_id}_{call.message.message_id}"),
                               types.InlineKeyboardButton("🆘 Thêm người hỗ trợ", callback_data=f"asksupport_{ticket_id}_{call.message.message_id}"))
                    markup.add(types.InlineKeyboardButton("🔙 Trả lại (Hủy nhận)", callback_data=f"abort_{ticket_id}_{call.message.message_id}"))
                    msg_to_it = f"🚀 **[LÀM CHÍNH] YÊU CẦU #{ticket_id}**\n👤 Khách: {res[1]}\n🏢 Phòng: {res[2]}\n📝 Lỗi: {res[3]}\n👉 Chat trực tiếp với khách bên dưới:"
                    sent_it_msg = current_bot.send_message(it_id, msg_to_it, reply_markup=markup, parse_mode="Markdown")
                except: 
                    cursor.execute("UPDATE tickets SET it_id = NULL, it_name = NULL, status = 'Mới' WHERE id = ?", (ticket_id,))
                    conn.commit()
                    current_bot.answer_callback_query(call.id, "❌ Nhắn tin riêng với Bot hoặc gõ /setworkspace trong nhóm riêng trước!", show_alert=True); conn.close(); return

            cursor.execute('UPDATE tickets SET group_msg_id = ?, it_msg_id = ?, topic_id = ? WHERE id = ?', (call.message.message_id, sent_it_msg.message_id, topic_id, ticket_id))
            
            cursor.execute("SELECT count(*) FROM tickets WHERE status = 'Mới'")
            if cursor.fetchone()[0] == 0:
                if bot_config.last_reminder_msg_id:
                    try: current_bot.delete_message(bot_config.GROUP_IT_ID, bot_config.last_reminder_msg_id)
                    except: pass
                    bot_config.last_reminder_msg_id = None
            
            cursor.execute("INSERT OR REPLACE INTO active_sessions (user_id, ticket_id, role) VALUES (?, ?, 'customer')", (user_id, ticket_id))
            cursor.execute("INSERT OR REPLACE INTO active_sessions (user_id, ticket_id, role, topic_id) VALUES (?, ?, 'main', ?)", (it_id, ticket_id, topic_id))
            conn.commit()
            bot_config.ticket_last_status[int(ticket_id)] = 'Đang xử lý'

            text_proc = f"🚨 **YÊU CẦU #{ticket_id}**\n👤 Khách: {res[1]}\n🏢 Phòng: {res[2]}\n📝 Lỗi: {res[3]}\n\n⏳ **Đang xử lý**\n👨‍💻 **IT Chính:** {it_info[0]}"
            markup_jump = None
            if topic_url:
                markup_jump = types.InlineKeyboardMarkup()
                markup_jump.add(types.InlineKeyboardButton(f"🚀 Đi tới Topic (Chỉ {it_info[0]} vào được)", url=topic_url))

            safe_edit_message(current_bot, bot_config.GROUP_IT_ID, call.message.message_id, text_proc, reply_markup=markup_jump)
            
            current_bot.send_message(user_id, f"👨‍💻 IT **{it_info[0]}** đang hỗ trợ bạn. Vui lòng giữ kết nối.", parse_mode="Markdown")
            current_bot.answer_callback_query(call.id, f"✅ Đã nhận việc! Nhấn nút 'Đi tới Topic' ngay bên dưới để chat.")

        elif action == 'asksupport':
            current_bot.answer_callback_query(call.id, "Đã gửi yêu cầu hỗ trợ vào nhóm IT!")
            markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤝 Tham gia hỗ trợ", callback_data=f"join_{ticket_id}"))
            cursor.execute('SELECT user_name, dept, issue, it_name FROM tickets WHERE id = ?', (ticket_id,))
            res = cursor.fetchone()
            if res:
                text_help = f"🚨 **YÊU CẦU #{ticket_id} ĐANG CẦN SUPPORT** 🆘\n👤 Khách: {res[0]}\n🏢 Phòng: {res[1]}\n📝 Lỗi: {res[2]}\n\n👨‍💻 **IT Chính:** {res[3]} đang cần đồng đội hỗ trợ ca này!"
                sent_msg = current_bot.send_message(bot_config.GROUP_IT_ID, text_help, reply_markup=markup, parse_mode="Markdown")
                cursor.execute('UPDATE tickets SET group_support_msg_id = ? WHERE id = ?', (sent_msg.message_id, ticket_id))
                conn.commit()

        elif action == 'join':
            cursor.execute("SELECT role FROM active_sessions WHERE user_id = ? AND ticket_id = ?", (it_id, ticket_id))
            role_exist = cursor.fetchone()
            if role_exist:
                if role_exist[0] == 'main':
                    current_bot.answer_callback_query(call.id, "❌ Bạn đang là IT Chính của Ticket này rồi!", show_alert=True)
                else:
                    current_bot.answer_callback_query(call.id, "❌ Bạn đã ở trong Ticket này rồi!", show_alert=True)
                conn.close(); return
                
            workspace_id = it_info[2] if it_info and len(it_info) > 2 and it_info[2] else None
            if not workspace_id:
                cursor.execute("SELECT ticket_id FROM active_sessions WHERE user_id = ?", (it_id,))
                if cursor.fetchone():
                    current_bot.answer_callback_query(call.id, "❌ BẠN ĐANG BẬN xử lý Ticket khác! Hãy tạo Nhóm Workspace riêng để làm việc đa nhiệm.", show_alert=True); conn.close(); return

            cursor.execute('SELECT support_it_ids, support_it_names, user_name FROM tickets WHERE id = ?', (ticket_id,))
            res = cursor.fetchone()
            if not res: current_bot.answer_callback_query(call.id, "❌ Ticket không tồn tại!", show_alert=True); conn.close(); return
            
            old_ids = res[0]
            old_names = res[1]
            cust_name = res[2]
            s_ids = f"{old_ids},{it_id}" if old_ids else str(it_id)
            s_names = f"{old_names}, {it_info[0]}" if old_names else it_info[0]
            
            if old_ids is None:
                cursor.execute('UPDATE tickets SET support_it_ids = ?, support_it_names = ? WHERE id = ? AND support_it_ids IS NULL', (s_ids, s_names, ticket_id))
            else:
                cursor.execute('UPDATE tickets SET support_it_ids = ?, support_it_names = ? WHERE id = ? AND support_it_ids = ?', (s_ids, s_names, ticket_id, old_ids))
                
            if cursor.rowcount == 0:
                current_bot.answer_callback_query(call.id, "❌ Có người khác vừa bấm, vui lòng bấm lại!", show_alert=True); conn.close(); return
            
            topic_id = None
            workspace_id = it_info[2] if it_info and len(it_info) > 2 and it_info[2] else None
            
            if workspace_id:
                try:
                    topic_name = f"🤝 [HỖ TRỢ] #{ticket_id} - {cust_name}"[:120]
                    topic = current_bot.create_forum_topic(chat_id=workspace_id, name=topic_name)
                    topic_id = topic.message_thread_id
                    markup_leave = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🏃‍♂️ Rời hỗ trợ", callback_data=f"leave_{ticket_id}"))
                    sent_sup_msg = current_bot.send_message(workspace_id, f"🚀 **[HỖ TRỢ] YÊU CẦU #{ticket_id}**\nĐã tham gia hỗ trợ. Bạn có thể chat ngay tại đây.", reply_markup=markup_leave, parse_mode="Markdown", message_thread_id=topic_id)
                except Exception as e:
                    workspace_id = None
                    
            if not workspace_id:
                markup_leave = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🏃‍♂️ Rời hỗ trợ", callback_data=f"leave_{ticket_id}"))
                try: current_bot.send_message(it_id, f"🚀 **[HỖ TRỢ] YÊU CẦU #{ticket_id}**\nĐã tham gia nhóm chat của ticket này. Bạn có thể chat ngay.", reply_markup=markup_leave, parse_mode="Markdown")
                except: pass
            
            cursor.execute("INSERT OR REPLACE INTO active_sessions (user_id, ticket_id, role, topic_id) VALUES (?, ?, 'support', ?)", (it_id, ticket_id, topic_id))
            conn.commit()

            try: current_bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            except: pass

            cursor.execute("SELECT user_id, role, topic_id FROM active_sessions WHERE ticket_id = ?", (ticket_id,))
            for p_id, role, p_topic in cursor.fetchall():
                try:
                    if role == 'customer': current_bot.send_message(p_id, f"👨‍🔧 IT **{it_info[0]}** vừa tham gia hỗ trợ.", parse_mode="Markdown")
                    elif role == 'main': 
                        target_chat = p_id
                        target_thread = None
                        if p_topic:
                            cursor.execute("SELECT workspace_group_id FROM it_staff WHERE it_id = ?", (p_id,))
                            ws = cursor.fetchone()
                            if ws and ws[0]:
                                target_chat = ws[0]
                                target_thread = p_topic
                        current_bot.send_message(target_chat, f"👨‍🔧 Đồng đội **{it_info[0]}** vừa vào hỗ trợ bạn.", parse_mode="Markdown", message_thread_id=target_thread)
                except: pass
            
            current_bot.answer_callback_query(call.id, "✅ Đã tham gia hỗ trợ Ticket này!")

        elif action == 'leave':
            cursor.execute("SELECT role, topic_id FROM active_sessions WHERE user_id = ? AND ticket_id = ?", (it_id, ticket_id))
            role_chk = cursor.fetchone()
            if not role_chk or role_chk[0] != 'support':
                current_bot.answer_callback_query(call.id, "❌ Bạn không phải người hỗ trợ ticket này!", show_alert=True); conn.close(); return

            topic_id = role_chk[1]
            cursor.execute("DELETE FROM active_sessions WHERE user_id = ? AND ticket_id = ?", (it_id, ticket_id))
            
            cursor.execute('SELECT support_it_ids, support_it_names FROM tickets WHERE id = ?', (ticket_id,))
            res = cursor.fetchone()
            if res:
                ids_list = [x for x in (res[0] or "").split(',') if x and x != str(it_id)]
                names_list = [x.strip() for x in (res[1] or "").split(',') if x.strip() and x.strip() != it_info[0]]
                
                new_ids = ",".join(ids_list) if ids_list else None
                new_names = ", ".join(names_list) if names_list else None
                cursor.execute('UPDATE tickets SET support_it_ids = ?, support_it_names = ? WHERE id = ?', (new_ids, new_names, ticket_id))
            conn.commit()

            try: current_bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            except: pass
            
            if topic_id and it_info[2]:
                try: current_bot.edit_forum_topic(chat_id=it_info[2], message_thread_id=topic_id, name=f"🏃‍♂️ [ĐÃ RỜI] #{ticket_id}"[:120])
                except: pass
                try: current_bot.send_message(it_info[2], f"🔙 Bạn đã rời khỏi nhóm hỗ trợ Ticket #{ticket_id}.", message_thread_id=topic_id)
                except: pass
                try: current_bot.close_forum_topic(chat_id=it_info[2], message_thread_id=topic_id)
                except: pass
            else:
                try: current_bot.send_message(it_id, f"🔙 Bạn đã rời khỏi nhóm hỗ trợ Ticket #{ticket_id}.")
                except: pass
            
            cursor.execute("SELECT user_id, role, topic_id FROM active_sessions WHERE ticket_id = ?", (ticket_id,))
            for p_id, role, p_topic in cursor.fetchall():
                try:
                    if role == 'customer': current_bot.send_message(p_id, f"👨‍🔧 IT hỗ trợ **{it_info[0]}** đã rời khỏi cuộc trò chuyện.", parse_mode="Markdown")
                    elif role == 'main':
                        target_chat = p_id
                        target_thread = None
                        if p_topic:
                            cursor.execute("SELECT workspace_group_id FROM it_staff WHERE it_id = ?", (p_id,))
                            ws = cursor.fetchone()
                            if ws and ws[0]:
                                target_chat = ws[0]
                                target_thread = p_topic
                        current_bot.send_message(target_chat, f"👨‍🔧 Đồng đội **{it_info[0]}** đã rời khỏi nhóm hỗ trợ.", parse_mode="Markdown", message_thread_id=target_thread)
                except: pass
            
            current_bot.answer_callback_query(call.id, "Đã rời Ticket thành công!")

        elif action == 'abort':
            group_msg_id = parts[2] if len(parts) > 2 else None
            cursor.execute("SELECT user_id, role, topic_id FROM active_sessions WHERE ticket_id = ?", (ticket_id,))
            participants = cursor.fetchall()
            cursor.execute("DELETE FROM active_sessions WHERE ticket_id = ?", (ticket_id,))
            cursor.execute('SELECT user_name, dept, issue, group_support_msg_id, topic_id, it_id, group_msg_id FROM tickets WHERE id = ?', (ticket_id,))
            res = cursor.fetchone()
            
            if group_msg_id:
                try: current_bot.delete_message(bot_config.GROUP_IT_ID, group_msg_id)
                except: pass
            if res and res[3]:
                try: current_bot.delete_message(bot_config.GROUP_IT_ID, res[3])
                except: pass
            
            try: current_bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            except: pass
            
            for p_id, role, p_topic in participants:
                if role in ['main', 'support']:
                    if p_topic:
                        cursor.execute("SELECT workspace_group_id FROM it_staff WHERE it_id = ?", (p_id,))
                        ws_row = cursor.fetchone()
                        if ws_row and ws_row[0]:
                            name_prefix = "❌ [TRẢ LẠI]" if role == 'main' else "🛑 [HỦY]"
                            try: current_bot.edit_forum_topic(chat_id=ws_row[0], message_thread_id=p_topic, name=f"{name_prefix} #{ticket_id} - {res[0]}"[:120])
                            except: pass
                            try: current_bot.send_message(ws_row[0], "🔙 Ticket đã bị nhả/hủy.", message_thread_id=p_topic)
                            except: pass
                            try: current_bot.close_forum_topic(chat_id=ws_row[0], message_thread_id=p_topic)
                            except: pass
                    else:
                        try: current_bot.send_message(p_id, "🔙 Bạn đã nhả/rời Ticket thành công.")
                        except: pass
                elif role == 'customer':
                    try: current_bot.send_message(p_id, "⚠️ IT hiện tại đang bận xử lý khẩn cấp, sự cố của bạn đã chuyển lại cho team!")
                    except: pass
            
            current_bot.answer_callback_query(call.id, "Đã nhả Ticket thành công!")
            
            if res:
                text_repost = f"🚨 **TICKET #{ticket_id} BỊ TRẢ LẠI**\n👤 Khách: {res[0]}\n🏢 Phòng: {res[1]}\n📝 Lỗi: {res[2]}"
                markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤝 Nhận việc", callback_data=f"claim_{ticket_id}"))
                sent_msg = current_bot.send_message(bot_config.GROUP_IT_ID, text_repost, reply_markup=markup, parse_mode="Markdown")
                try: current_bot.pin_chat_message(chat_id=bot_config.GROUP_IT_ID, message_id=sent_msg.message_id, disable_notification=True)
                except: pass
                cursor.execute("UPDATE tickets SET it_id=NULL, it_name=NULL, support_it_ids=NULL, support_it_names=NULL, status='Mới', group_msg_id=?, it_msg_id=NULL, topic_id=NULL WHERE id=?", (sent_msg.message_id, ticket_id))
                conn.commit()
                bot_config.ticket_last_status[int(ticket_id)] = 'Mới'

        elif action == 'done':
            cursor.execute("SELECT role FROM active_sessions WHERE user_id = ? AND ticket_id = ?", (it_id, ticket_id))
            role_chk = cursor.fetchone()
            
            cursor.execute("SELECT it_id, user_name, dept, issue, it_name, support_it_names, group_support_msg_id, group_msg_id, topic_id FROM tickets WHERE id = ?", (ticket_id,))
            res = cursor.fetchone()
            
            if not role_chk or role_chk[0] != 'main':
                if not res or res[0] != it_id:
                    current_bot.answer_callback_query(call.id, "❌ Chỉ IT Làm Chính mới được Đóng Ticket!", show_alert=True); conn.close(); return

            cursor.execute("SELECT user_id, role, topic_id FROM active_sessions WHERE ticket_id = ?", (ticket_id,))
            participants = cursor.fetchall()
            cursor.execute("DELETE FROM active_sessions WHERE ticket_id = ?", (ticket_id,))

            completed_time = get_adjusted_time().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("UPDATE tickets SET status = 'Hoàn thành', completed_at = ? WHERE id = ?", (completed_time, ticket_id))
            conn.commit()
            bot_config.ticket_last_status[int(ticket_id)] = 'Hoàn thành'

            try: current_bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            except: pass

            if res and res[6]: 
                try: current_bot.delete_message(bot_config.GROUP_IT_ID, res[6])
                except: pass
            
            if res and res[7]: 
                try: current_bot.unpin_chat_message(chat_id=bot_config.GROUP_IT_ID, message_id=res[7])
                except: pass

            for p_id, role, p_topic in participants:
                if role in ['main', 'support']:
                    target_topic = p_topic if p_topic else (res[8] if role == 'main' else None)
                    if target_topic:
                        cursor.execute("SELECT workspace_group_id FROM it_staff WHERE it_id = ?", (p_id,))
                        ws_row = cursor.fetchone()
                        if ws_row and ws_row[0]:
                            try: current_bot.edit_forum_topic(chat_id=ws_row[0], message_thread_id=target_topic, name=f"✅ [ĐÃ XONG] #{ticket_id} - {res[1]}"[:120])
                            except: pass
                            try: current_bot.send_message(ws_row[0], "🎉 Đã đóng Ticket thành công.", message_thread_id=target_topic)
                            except: pass
                            try: current_bot.close_forum_topic(chat_id=ws_row[0], message_thread_id=target_topic)
                            except: pass
                    else:
                        msg = f"🎉 Đã đóng Ticket **#{ticket_id}**." if role == 'main' else f"🎉 Ticket **#{ticket_id}** đã được đóng bởi IT Chính."
                        try: current_bot.send_message(p_id, msg)
                        except: pass
                elif role == 'customer':
                    try:
                        current_bot.send_message(p_id, f"✅ **Sự cố của bạn đã hoàn tất.**\nVui lòng đánh giá dịch vụ:", reply_markup=get_rating_keyboard(ticket_id), parse_mode="Markdown")
                        current_bot.send_message(p_id, "👇 Báo sự cố khác:", reply_markup=get_report_keyboard())
                    except: pass
                    
            current_bot.answer_callback_query(call.id, "✅ Đã đóng Ticket!")

            if len(parts) > 2 and res:
                sup_text = f"\n👨‍🔧 **Hỗ trợ:** {res[5]}" if res[5] else ""
                text_fin = f"🚨 **YÊU CẦU #{ticket_id}**\n👤 Khách: {res[1]}\n🏢 Phòng: {res[2]}\n📝 Lỗi: {res[3]}\n\n✅ **Hoàn thành**\n👨‍💻 **IT Chính:** {res[4]}{sup_text}"
                safe_edit_message(current_bot, bot_config.GROUP_IT_ID, parts[2], text_fin)
            
        conn.close()