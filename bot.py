import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import threading
import time
import sys

ticket_last_status = {} 

bot = None
TOKEN = None
GROUP_IT_ID = None
TIME_OFFSET = 0  
is_running = True
last_reminder_msg_id = None 

# HÀM KẾT NỐI DATABASE
def connect_db():
    conn = sqlite3.connect('helpdesk.db', timeout=20, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def init_db():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, user_name TEXT, dept TEXT, issue TEXT, status TEXT, it_id INTEGER, it_name TEXT, created_at TEXT, rating INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, dept TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS it_staff (it_id INTEGER PRIMARY KEY, it_real_name TEXT, it_phone TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS departments (id INTEGER PRIMARY KEY, name TEXT UNIQUE, topic_id INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    
    cursor.execute('CREATE TABLE IF NOT EXISTS active_sessions (user_id INTEGER PRIMARY KEY, ticket_id INTEGER, role TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS user_states_db (user_id INTEGER PRIMARY KEY, step TEXT, temp_data TEXT)')
    
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN rating INTEGER')
    except: pass
    try: cursor.execute('ALTER TABLE it_staff ADD COLUMN it_phone TEXT')
    except: pass
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN it_name TEXT')
    except: pass 
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN support_it_ids TEXT')
    except: pass 
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN support_it_names TEXT')
    except: pass 
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN group_support_msg_id INTEGER')
    except: pass 
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN group_msg_id INTEGER') 
    except: pass
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN it_msg_id INTEGER')
    except: pass
    
    conn.commit()
    conn.close()

init_db()

# --- HÀM QUẢN LÝ STATE ---
def set_state(uid, step, temp_data=None):
    conn = connect_db()
    conn.execute("INSERT OR REPLACE INTO user_states_db (user_id, step, temp_data) VALUES (?, ?, ?)", (uid, step, temp_data))
    conn.commit(); conn.close()

def get_state(uid):
    conn = connect_db()
    row = conn.execute("SELECT step, temp_data FROM user_states_db WHERE user_id = ?", (uid,)).fetchone()
    conn.close()
    return row if row else (None, None)

def clear_state(uid):
    conn = connect_db()
    conn.execute("DELETE FROM user_states_db WHERE user_id = ?", (uid,))
    conn.commit(); conn.close()

def get_adjusted_time():
    return datetime.now() + timedelta(seconds=TIME_OFFSET)

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

def sync_hubs_with_db():
    global bot, GROUP_IT_ID, is_running, ticket_last_status
    try:
        conn = connect_db(); cursor = conn.cursor()
        cursor.execute("SELECT id, status FROM tickets WHERE status != 'Hoàn thành'")
        for row in cursor.fetchall(): ticket_last_status[row[0]] = row[1]
        conn.close()
    except: pass
    
    while is_running:
        try:
            time.sleep(5)
            active_ids = [tid for tid, stat in ticket_last_status.items() if stat != 'Hoàn thành']
            conn = connect_db(); cursor = conn.cursor()
            
            if active_ids:
                placeholders = ",".join("?" for _ in active_ids)
                query = f"SELECT id, status, user_name, dept, issue, it_name, support_it_names, group_msg_id, it_id, it_msg_id FROM tickets WHERE status != 'Hoàn thành' OR id IN ({placeholders})"
                cursor.execute(query, active_ids)
            else:
                cursor.execute("SELECT id, status, user_name, dept, issue, it_name, support_it_names, group_msg_id, it_id, it_msg_id FROM tickets WHERE status != 'Hoàn thành'")
                
            rows = cursor.fetchall()
            current_db_status = {}
            for row in rows:
                t_id, status = row[0], row[1]
                current_db_status[t_id] = status
                if t_id not in ticket_last_status: ticket_last_status[t_id] = status
                
                if ticket_last_status[t_id] != status:
                    g_msg_id, it_id_db, it_msg_id_db = row[7], row[8], row[9]
                    
                    if bot and GROUP_IT_ID:
                        if status == 'Hoàn thành':
                            if it_id_db and it_msg_id_db:
                                try: bot.edit_message_reply_markup(chat_id=it_id_db, message_id=it_msg_id_db, reply_markup=None)
                                except: pass
                            if g_msg_id:
                                sup_text = f"\n👨‍🔧 **Hỗ trợ:** {row[6]}" if row[6] else ""
                                text_fin = f"🚨 **YÊU CẦU #{t_id}**\n👤 Khách: {row[2]}\n🏢 Phòng: {row[3]}\n📝 Lỗi: {row[4]}\n\n✅ **Hoàn thành**\n👨‍💻 **IT Chính:** {row[5] or 'N/A'}{sup_text}"
                                safe_edit_message(bot, GROUP_IT_ID, g_msg_id, text_fin)
                            
                            cursor.execute("SELECT user_id, role FROM active_sessions WHERE ticket_id = ?", (t_id,))
                            participants = cursor.fetchall()
                            if participants:
                                cursor.execute("DELETE FROM active_sessions WHERE ticket_id = ?", (t_id,))
                                conn.commit()
                                for p_id, role in participants:
                                    try:
                                        if role in ['main', 'support']: bot.send_message(p_id, f"🎉 Ticket **#{t_id}** đã được đóng từ Web Dashboard.")
                                        elif role == 'customer':
                                            bot.send_message(p_id, f"✅ **Sự cố của bạn đã hoàn tất.**\nVui lòng đánh giá dịch vụ:", reply_markup=get_rating_keyboard(t_id), parse_mode="Markdown")
                                            bot.send_message(p_id, "👇 Báo sự cố khác:", reply_markup=get_report_keyboard())
                                    except: pass

                        elif status == 'Đang xử lý':
                            if g_msg_id:
                                text_proc = f"🚨 **YÊU CẦU #{t_id}**\n👤 Khách: {row[2]}\n🏢 Phòng: {row[3]}\n📝 Lỗi: {row[4]}\n\n⏳ **Đang xử lý**\n👨‍💻 **IT Chính:** {row[5] or 'N/A'}"
                                safe_edit_message(bot, GROUP_IT_ID, g_msg_id, text_proc)
                            
                        elif status == 'Mới':
                            if it_id_db and it_msg_id_db:
                                try: bot.edit_message_reply_markup(chat_id=it_id_db, message_id=it_msg_id_db, reply_markup=None)
                                except: pass
                            if g_msg_id:
                                text_new = f"🚨 **YÊU CẦU #{t_id} (TRẢ LẠI / CHỜ NHẬN)**\n👤 Khách: {row[2]}\n🏢 Phòng: {row[3]}\n📝 Lỗi: {row[4]}"
                                markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤝 Nhận việc (Làm chính)", callback_data=f"claim_{t_id}"))
                                safe_edit_message(bot, GROUP_IT_ID, g_msg_id, text_new, markup)
                            
                            cursor.execute("SELECT user_id, role FROM active_sessions WHERE ticket_id = ?", (t_id,))
                            participants = cursor.fetchall()
                            if participants:
                                cursor.execute("DELETE FROM active_sessions WHERE ticket_id = ?", (t_id,))
                                conn.commit()
                                for p_id, role in participants:
                                    try:
                                        if role in ['main', 'support']: bot.send_message(p_id, f"🔙 Ticket **#{t_id}** đã bị Quản lý hủy nhận việc từ Web Dashboard.")
                                        elif role == 'customer': bot.send_message(p_id, "⚠️ IT hiện tại đang bận, sự cố của bạn đã được chuyển lại cho team. Sẽ có IT khác tiếp nhận ngay!")
                                    except: pass
                ticket_last_status[t_id] = status
            conn.close()

            current_ids = list(ticket_last_status.keys())
            for t_id in current_ids:
                if t_id not in current_db_status or current_db_status[t_id] == 'Hoàn thành':
                    ticket_last_status.pop(t_id, None)
        except: pass

notified_tickets = set()

def auto_remind_it():
    global bot, GROUP_IT_ID, is_running, last_reminder_msg_id
    while is_running:
        try:
            time.sleep(60) 
            if not bot or not GROUP_IT_ID: continue
            conn = connect_db(); cursor = conn.cursor()
            fifteen_mins_ago = (get_adjusted_time() - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("SELECT id FROM tickets WHERE status = 'Mới' AND created_at < ?", (fifteen_mins_ago,))
            rows = cursor.fetchall(); conn.close()
            
            to_notify = []
            for r in rows:
                if r[0] not in notified_tickets:
                    to_notify.append(r[0])
                    notified_tickets.add(r[0]) 
                    
            if to_notify:
                ids = ", ".join([f"#{tid}" for tid in to_notify])
                if last_reminder_msg_id:
                    try: bot.delete_message(GROUP_IT_ID, last_reminder_msg_id)
                    except: pass
                msg = bot.send_message(GROUP_IT_ID, f"📢 **THÔNG BÁO NHẮC VIỆC KHẨN CẤP!**\n\nCác sự cố {ids} đã treo hơn 15 phút. Anh em kiểm tra gấp! 🔥", parse_mode="Markdown")
                last_reminder_msg_id = msg.message_id 
        except: pass

def get_config_from_db():
    conn = connect_db(); cursor = conn.cursor()
    token_row = cursor.execute("SELECT value FROM settings WHERE key='BOT_TOKEN'").fetchone()
    group_row = cursor.execute("SELECT value FROM settings WHERE key='GROUP_IT_ID'").fetchone()
    offset_row = cursor.execute("SELECT value FROM settings WHERE key='TIME_OFFSET'").fetchone()
    conn.close()
    t = token_row[0].strip() if token_row else None
    g = group_row[0].strip() if group_row else None
    o = int(offset_row[0]) if offset_row else 0
    return t, g, o

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

def setup_bot_handlers(current_bot):

    @current_bot.message_handler(commands=['getid'])
    def get_exact_id(message):
        current_bot.send_message(message.chat.id, f"🎯 ID CHÍNH XÁC CỦA NHÓM NÀY LÀ:\n\n`{message.chat.id}`\n\n👉 Copy DÃY SỐ TRÊN dán vào Web!", parse_mode="Markdown")

    @current_bot.message_handler(commands=['pending'])
    def check_pending(message):
        if message.chat.id != GROUP_IT_ID: return 
        conn = connect_db(); cursor = conn.cursor()
        cursor.execute("SELECT id, user_name, dept, created_at FROM tickets WHERE status = 'Mới'")
        rows = cursor.fetchall(); conn.close()

        if not rows: current_bot.send_message(GROUP_IT_ID, "✅ Không còn sự cố nào đang chờ tiếp nhận.")
        else:
            text = "⚠️ **DANH SÁCH SỰ CỐ ĐANG CHỜ:**\n\n"
            for r in rows: text += f"🔹 **#{r[0]}** - {r[1]} - {r[2]} - *{r[3][11:16]}*\n"
            current_bot.send_message(GROUP_IT_ID, text, parse_mode="Markdown")

    @current_bot.message_handler(content_types=['new_chat_members'])
    def welcome_new_it_member(message):
        if message.chat.id != GROUP_IT_ID: return
        auth_url = f"https://t.me/{current_bot.get_me().username}?start=iam_it"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("👨‍💻 Bấm vào đây để Xác Thực IT", url=auth_url))
        for new_member in message.new_chat_members:
            if not new_member.is_bot: 
                user_name = new_member.first_name + (f" {new_member.last_name}" if new_member.last_name else "")
                text = f"👋 Chào mừng đồng đội mới [{user_name}](tg://user?id={new_member.id})!\n\n🚨 Hãy nhấn nút bên dưới và bấm **Start** xác thực."
                current_bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

    @current_bot.message_handler(commands=['setup_it'])
    def setup_it_group(message):
        if message.chat.id != GROUP_IT_ID: return
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
        conn = connect_db(); cursor = conn.cursor()
        
        if len(args) > 1:
            if args[1] == 'it_support': return
            if args[1] == 'iam_it': 
                set_state(message.from_user.id, 'waiting_for_it_name')
                current_bot.send_message(message.chat.id, "👨‍💻 **XÁC THỰC IT:** Nhập **Họ tên hiển thị** của bạn:", parse_mode="Markdown")
                conn.close(); return
            try:
                dept = bytes.fromhex(args[1]).decode('utf-8')
                cursor.execute('INSERT OR REPLACE INTO users (user_id, name, dept) VALUES (?, ?, ?)', (message.from_user.id, message.from_user.full_name, dept))
                conn.commit()
                set_state(message.from_user.id, 'waiting_for_issue')
                markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Hủy báo cáo", callback_data="cancelReport"))
                current_bot.send_message(message.chat.id, f"✅ **Hệ thống IT - {dept}** chào bạn!\n\nMời bạn mô tả lỗi tại đây.", reply_markup=markup, parse_mode="Markdown")
            except: pass
        else:
            cursor.execute('SELECT it_real_name FROM it_staff WHERE it_id = ?', (message.from_user.id,))
            if cursor.fetchone():
                current_bot.send_message(message.chat.id, "👨‍💻 Chào IT. Tài khoản đã xác thực.\nHãy theo dõi nhóm tổng để nhận việc nhé!")
            else:
                cursor.execute('SELECT name, dept FROM users WHERE user_id = ?', (message.from_user.id,))
                user = cursor.fetchone()
                if user: 
                    current_bot.send_message(message.chat.id, f"👋 Chào **{user[0]}** - Phòng: **{user[1]}**.", reply_markup=get_report_keyboard(), parse_mode="Markdown")
                else:
                    set_state(message.from_user.id, 'ask_name')
                    current_bot.send_message(message.chat.id, "👋 Chào mừng bạn! Cho biết **Họ và Tên** của bạn:")
        conn.close()

    @current_bot.message_handler(content_types=['text', 'photo', 'document', 'video', 'audio', 'voice'])
    def handle_all_messages(message):
        if message.chat.id == GROUP_IT_ID: 
            try: current_bot.delete_message(message.chat.id, message.message_id)
            except: pass
            return 
        
        if message.chat.type != 'private': return
        if message.text and message.text.startswith('/'): return
        sender_id = message.chat.id
        
        step, temp_data = get_state(sender_id)
        
        # 1. ĐĂNG KÝ
        if step:
            if step == 'waiting_for_it_name':
                set_state(sender_id, 'waiting_for_it_phone', message.text)
                current_bot.send_message(sender_id, f"📱 Chào **{message.text}**, nhập **Số điện thoại** của bạn:", parse_mode="Markdown")
                return
            elif step == 'waiting_for_it_phone':
                it_name, it_phone = temp_data, message.text
                conn = connect_db(); conn.execute('INSERT OR REPLACE INTO it_staff (it_id, it_real_name, it_phone) VALUES (?, ?, ?)', (sender_id, it_name, it_phone)); conn.commit(); conn.close()
                clear_state(sender_id)
                current_bot.send_message(sender_id, f"✅ Xác thực thành công!\n👤 {it_name} - 📞 {it_phone}")
                return

        # 2. ĐỊNH TUYẾN CHAT
        conn = connect_db(); cursor = conn.cursor()
        cursor.execute("SELECT ticket_id, role FROM active_sessions WHERE user_id = ?", (sender_id,))
        active_session = cursor.fetchone()
        
        if active_session:
            t_id, role = active_session[0], active_session[1]
            if role == 'customer': prefix = "👤 **Khách:** "
            elif role == 'main': prefix = "👨‍💻 **IT Chính:** "
            else: prefix = "👨‍🔧 **IT Hỗ trợ:** "

            cursor.execute("SELECT user_id FROM active_sessions WHERE ticket_id = ?", (t_id,))
            for (p_id,) in cursor.fetchall():
                if p_id != sender_id:
                    try:
                        if message.content_type == 'text': current_bot.send_message(p_id, f"{prefix}{message.text}", parse_mode="Markdown")
                        elif message.content_type == 'photo': current_bot.send_photo(p_id, message.photo[-1].file_id, caption=f"{prefix}{message.caption or ''}", parse_mode="Markdown")
                        elif message.content_type == 'document': current_bot.send_document(p_id, message.document.file_id, caption=f"{prefix}{message.caption or ''}", parse_mode="Markdown")
                        elif message.content_type == 'video': current_bot.send_video(p_id, message.video.file_id, caption=f"{prefix}{message.caption or ''}", parse_mode="Markdown")
                        elif message.content_type == 'voice': current_bot.send_voice(p_id, message.voice.file_id, caption=f"{prefix}{message.caption or ''}", parse_mode="Markdown")
                        elif message.content_type == 'audio': current_bot.send_audio(p_id, message.audio.file_id, caption=f"{prefix}{message.caption or ''}", parse_mode="Markdown")
                    except: pass
            conn.close(); return
            
        cursor.execute('SELECT it_real_name FROM it_staff WHERE it_id = ?', (sender_id,))
        is_it = cursor.fetchone()
        if is_it:
            current_bot.send_message(sender_id, f"👨‍💻 Chào IT **{is_it[0]}**. Bạn hiện không xử lý sự cố nào.", parse_mode="Markdown")
            conn.close(); return

        cursor.execute('SELECT name, dept FROM users WHERE user_id = ?', (sender_id,))
        user = cursor.fetchone()
        
        if not user:
            if not step:
                set_state(sender_id, 'ask_name')
                current_bot.send_message(sender_id, "Cho biết **Họ tên** của bạn:")
            elif step == 'ask_name':
                set_state(sender_id, 'ask_dept', message.text)
                cursor.execute("SELECT name FROM departments")
                depts = [row[0] for row in cursor.fetchall()]
                if depts:
                    markup = types.InlineKeyboardMarkup(row_width=1) 
                    for d in depts: markup.add(types.InlineKeyboardButton(d, callback_data=f"seldept_{d}"))
                    current_bot.send_message(sender_id, f"Chào **{message.text}**! Chọn **Phòng ban**:", reply_markup=markup, parse_mode="Markdown")
                else: current_bot.send_message(sender_id, "🏢 Nhập tên **Phòng ban** của bạn:")
            elif step == 'ask_dept':
                cursor.execute('INSERT INTO users (user_id, name, dept) VALUES (?, ?, ?)', (sender_id, temp_data, message.text))
                conn.commit(); clear_state(sender_id)
                current_bot.send_message(sender_id, "✅ Đã lưu!", reply_markup=get_report_keyboard())
            conn.close(); return

        cursor.execute("SELECT id FROM tickets WHERE user_id = ? AND status = 'Mới'", (sender_id,))
        pending_ticket = cursor.fetchone()
        if pending_ticket:
            current_bot.send_message(sender_id, f"⏳ Sự cố **#{pending_ticket[0]}** đang chờ tiếp nhận. Vui lòng không gửi thêm!", parse_mode="Markdown")
            conn.close(); return
            
        if step != 'waiting_for_issue':
            current_bot.send_message(sender_id, "👇 Nhấn nút báo sự cố:", reply_markup=get_report_keyboard()); conn.close(); return
            
        issue_text = message.text or message.caption or "Gửi đính kèm"
        cursor.execute('INSERT INTO tickets (user_id, user_name, dept, issue, status, created_at) VALUES (?, ?, ?, ?, ?, ?)', (sender_id, user[0], user[1], issue_text, 'Mới', get_adjusted_time().strftime("%Y-%m-%d %H:%M:%S")))
        ticket_id = cursor.lastrowid
        conn.commit(); clear_state(sender_id)
        
        current_bot.send_message(sender_id, "✅ **Đã gửi IT.** Vui lòng đợi.", parse_mode="Markdown")
        msg_to_it = f"🚨 **YÊU CẦU MỚI!**\n🆔 Mã: #{ticket_id}\n👤 Khách: {user[0]}\n🏢 Phòng: {user[1]}\n📝 Nội dung: {issue_text}"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤝 Nhận việc (Làm chính)", callback_data=f"claim_{ticket_id}"))
        
        sent_msg = None
        if message.content_type == 'photo': sent_msg = current_bot.send_photo(GROUP_IT_ID, message.photo[-1].file_id, caption=msg_to_it, reply_markup=markup, parse_mode="Markdown")
        elif message.content_type == 'video': sent_msg = current_bot.send_video(GROUP_IT_ID, message.video.file_id, caption=msg_to_it, reply_markup=markup, parse_mode="Markdown")
        elif message.content_type == 'document': sent_msg = current_bot.send_document(GROUP_IT_ID, message.document.file_id, caption=msg_to_it, reply_markup=markup, parse_mode="Markdown")
        elif message.content_type == 'voice': sent_msg = current_bot.send_voice(GROUP_IT_ID, message.voice.file_id, caption=msg_to_it, reply_markup=markup, parse_mode="Markdown")
        elif message.content_type == 'audio': sent_msg = current_bot.send_audio(GROUP_IT_ID, message.audio.file_id, caption=msg_to_it, reply_markup=markup, parse_mode="Markdown")
        else: sent_msg = current_bot.send_message(GROUP_IT_ID, msg_to_it, reply_markup=markup, parse_mode="Markdown")

        if sent_msg:
            cursor.execute("UPDATE tickets SET group_msg_id = ? WHERE id = ?", (sent_msg.message_id, ticket_id))
            conn.commit()
            ticket_last_status[ticket_id] = 'Mới'
        conn.close()

    @current_bot.callback_query_handler(func=lambda call: True)
    def callback_handler(call):
        if call.data == 'reportIssue':
            set_state(call.from_user.id, 'waiting_for_issue')
            markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Hủy báo cáo", callback_data="cancelReport"))
            try: current_bot.edit_message_text("📝 **Mời bạn mô tả lỗi:**\n*(Hoặc nhấn nút Hủy)*", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            except: pass
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
                cursor.execute("SELECT name FROM departments")
                depts = [row[0] for row in cursor.fetchall()]
                if depts:
                    markup = types.InlineKeyboardMarkup(row_width=1) 
                    for d in depts: markup.add(types.InlineKeyboardButton(d, callback_data=f"seldept_{d}"))
                    current_bot.edit_message_text(f"🔄 Đang cập nhật cho **{user[0]}**\nMời bạn chọn **Phòng ban** mới:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")
                else:
                    current_bot.edit_message_text("🏢 Vui lòng nhập tên **Phòng ban** mới của bạn:", chat_id=call.message.chat.id, message_id=call.message.message_id)
            conn.close(); return

        if call.data.startswith('seldept_'):
            dept_name = call.data[8:]
            sender_id = call.from_user.id
            step, temp_data = get_state(sender_id)
            if step == 'ask_dept':
                conn = connect_db(); cursor = conn.cursor()
                cursor.execute('INSERT OR REPLACE INTO users (user_id, name, dept) VALUES (?, ?, ?)', (sender_id, temp_data, dept_name))
                conn.commit(); conn.close()
                clear_state(sender_id)
                current_bot.edit_message_text(f"✅ Đã lưu thông tin!\n👤 Tên: **{temp_data}**\n🏢 Phòng ban: **{dept_name}**", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_report_keyboard(), parse_mode="Markdown")
            return

        parts = call.data.split('_')
        action, ticket_id = parts[0], parts[1]
        it_id = call.from_user.id

        if action == 'rate':
            conn = connect_db(); cursor = conn.cursor(); cursor.execute('UPDATE tickets SET rating = ? WHERE id = ?', (parts[2], ticket_id)); conn.commit(); conn.close()
            current_bot.edit_message_text(f"⭐ Đã đánh giá {parts[2]} sao!", chat_id=call.message.chat.id, message_id=call.message.message_id); return

        conn = connect_db(); cursor = conn.cursor()
        cursor.execute('SELECT it_real_name, it_phone FROM it_staff WHERE it_id = ?', (it_id,))
        it_info = cursor.fetchone()
        if not it_info and action in ['claim', 'join', 'leave']:
            current_bot.answer_callback_query(call.id, "❌ Chưa xác thực IT!", show_alert=True); conn.close(); return

        # ------------------
        # PHẦN VÁ LỖI XUNG ĐỘT (RACE CONDITION)
        # ------------------
        if action == 'claim':
            cursor.execute("SELECT ticket_id FROM active_sessions WHERE user_id = ?", (it_id,))
            if cursor.fetchone():
                current_bot.answer_callback_query(call.id, "❌ BẠN ĐANG BẬN xử lý Ticket khác!", show_alert=True); conn.close(); return

            # 1. ATOMIC UPDATE LÀM CHÍNH
            cursor.execute("UPDATE tickets SET it_id = ?, it_name = ?, status = 'Đang xử lý' WHERE id = ? AND status = 'Mới'", (it_id, it_info[0], ticket_id))
            if cursor.rowcount == 0:
                current_bot.answer_callback_query(call.id, "❌ Chậm tay! Đã có người nhận hoặc Ticket bị hủy.", show_alert=True); conn.close(); return
            
            cursor.execute('SELECT user_id, user_name, dept, issue FROM tickets WHERE id = ?', (ticket_id,))
            res = cursor.fetchone()
            user_id = res[0]
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ Hoàn thành", callback_data=f"done_{ticket_id}_{call.message.message_id}"),
                       types.InlineKeyboardButton("🆘 Thêm người hỗ trợ", callback_data=f"asksupport_{ticket_id}_{call.message.message_id}"))
            markup.add(types.InlineKeyboardButton("🔙 Trả lại (Hủy nhận)", callback_data=f"abort_{ticket_id}_{call.message.message_id}"))
            
            msg_to_it = f"🚀 **[LÀM CHÍNH] YÊU CẦU #{ticket_id}**\n👤 Khách: {res[1]}\n🏢 Phòng: {res[2]}\n📝 Lỗi: {res[3]}\n👉 Chat trực tiếp với khách bên dưới:"
            try: sent_it_msg = current_bot.send_message(it_id, msg_to_it, reply_markup=markup, parse_mode="Markdown")
            except: 
                cursor.execute("UPDATE tickets SET it_id = NULL, it_name = NULL, status = 'Mới' WHERE id = ?", (ticket_id,))
                conn.commit()
                current_bot.answer_callback_query(call.id, "❌ Nhắn tin riêng với Bot trước!", show_alert=True); conn.close(); return

            cursor.execute('UPDATE tickets SET group_msg_id = ?, it_msg_id = ? WHERE id = ?', (call.message.message_id, sent_it_msg.message_id, ticket_id))
            
            cursor.execute("SELECT count(*) FROM tickets WHERE status = 'Mới'")
            if cursor.fetchone()[0] == 0:
                global last_reminder_msg_id
                if last_reminder_msg_id:
                    try: current_bot.delete_message(GROUP_IT_ID, last_reminder_msg_id)
                    except: pass
                    last_reminder_msg_id = None
            
            cursor.execute("INSERT OR REPLACE INTO active_sessions (user_id, ticket_id, role) VALUES (?, ?, 'customer')", (user_id, ticket_id))
            cursor.execute("INSERT OR REPLACE INTO active_sessions (user_id, ticket_id, role) VALUES (?, ?, 'main')", (it_id, ticket_id))
            conn.commit()
            ticket_last_status[int(ticket_id)] = 'Đang xử lý'

            text_proc = f"🚨 **YÊU CẦU #{ticket_id}**\n👤 Khách: {res[1]}\n🏢 Phòng: {res[2]}\n📝 Lỗi: {res[3]}\n\n⏳ **Đang xử lý**\n👨‍💻 **IT Chính:** {it_info[0]}"
            safe_edit_message(current_bot, GROUP_IT_ID, call.message.message_id, text_proc)
            
            current_bot.send_message(user_id, f"👨‍💻 IT **{it_info[0]}** đang hỗ trợ bạn. Vui lòng giữ kết nối.", parse_mode="Markdown")
            current_bot.answer_callback_query(call.id, url=f"https://t.me/{(current_bot.get_me()).username}?start=it_support")

        elif action == 'asksupport':
            current_bot.answer_callback_query(call.id, "Đã gửi yêu cầu hỗ trợ vào nhóm IT!")
            markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤝 Tham gia hỗ trợ", callback_data=f"join_{ticket_id}"))
            cursor.execute('SELECT user_name, dept, issue, it_name FROM tickets WHERE id = ?', (ticket_id,))
            res = cursor.fetchone()
            if res:
                text_help = f"🚨 **YÊU CẦU #{ticket_id} ĐANG CẦN SUPPORT** 🆘\n👤 Khách: {res[0]}\n🏢 Phòng: {res[1]}\n📝 Lỗi: {res[2]}\n\n👨‍💻 **IT Chính:** {res[3]} đang cần đồng đội hỗ trợ ca này!"
                sent_msg = current_bot.send_message(GROUP_IT_ID, text_help, reply_markup=markup, parse_mode="Markdown")
                cursor.execute('UPDATE tickets SET group_support_msg_id = ? WHERE id = ?', (sent_msg.message_id, ticket_id))
                conn.commit()

        elif action == 'join':
            cursor.execute("SELECT role FROM active_sessions WHERE user_id = ? AND ticket_id = ?", (it_id, ticket_id))
            if cursor.fetchone():
                current_bot.answer_callback_query(call.id, "❌ Bạn đã ở trong Ticket này rồi!", show_alert=True); conn.close(); return
                
            cursor.execute("SELECT ticket_id FROM active_sessions WHERE user_id = ?", (it_id,))
            if cursor.fetchone():
                current_bot.answer_callback_query(call.id, "❌ BẠN ĐANG BẬN xử lý Ticket khác!", show_alert=True); conn.close(); return

            cursor.execute('SELECT support_it_ids, support_it_names FROM tickets WHERE id = ?', (ticket_id,))
            res = cursor.fetchone()
            if not res: current_bot.answer_callback_query(call.id, "❌ Ticket không tồn tại!", show_alert=True); conn.close(); return
            
            old_ids = res[0]
            old_names = res[1]
            s_ids = f"{old_ids},{it_id}" if old_ids else str(it_id)
            s_names = f"{old_names}, {it_info[0]}" if old_names else it_info[0]
            
            # 2. ATOMIC UPDATE THAM GIA HỖ TRỢ (Khóa Lạc Quan)
            if old_ids is None:
                cursor.execute('UPDATE tickets SET support_it_ids = ?, support_it_names = ? WHERE id = ? AND support_it_ids IS NULL', (s_ids, s_names, ticket_id))
            else:
                cursor.execute('UPDATE tickets SET support_it_ids = ?, support_it_names = ? WHERE id = ? AND support_it_ids = ?', (s_ids, s_names, ticket_id, old_ids))
                
            if cursor.rowcount == 0:
                current_bot.answer_callback_query(call.id, "❌ Có người khác vừa bấm, vui lòng bấm lại!", show_alert=True); conn.close(); return
            
            cursor.execute("INSERT OR REPLACE INTO active_sessions (user_id, ticket_id, role) VALUES (?, ?, 'support')", (it_id, ticket_id))
            conn.commit()

            try: current_bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            except: pass
            
            # BÀN PHÍM RỜI HỖ TRỢ CHO IT PHỤ
            markup_leave = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🏃‍♂️ Rời hỗ trợ", callback_data=f"leave_{ticket_id}"))
            try: current_bot.send_message(it_id, f"🚀 **[HỖ TRỢ] YÊU CẦU #{ticket_id}**\nĐã tham gia nhóm chat của ticket này. Bạn có thể chat ngay.", reply_markup=markup_leave, parse_mode="Markdown")
            except: pass
            
            cursor.execute("SELECT user_id, role FROM active_sessions WHERE ticket_id = ?", (ticket_id,))
            for p_id, role in cursor.fetchall():
                if role == 'customer': current_bot.send_message(p_id, f"👨‍🔧 IT **{it_info[0]}** vừa tham gia hỗ trợ.", parse_mode="Markdown")
                elif role == 'main': current_bot.send_message(p_id, f"👨‍🔧 Đồng đội **{it_info[0]}** vừa vào hỗ trợ bạn.", parse_mode="Markdown")
            
            current_bot.answer_callback_query(call.id, url=f"https://t.me/{(current_bot.get_me()).username}?start=it_support")

        # TÍNH NĂNG MỚI: RỜI HỖ TRỢ
        elif action == 'leave':
            cursor.execute("SELECT role FROM active_sessions WHERE user_id = ? AND ticket_id = ?", (it_id, ticket_id))
            role_chk = cursor.fetchone()
            if not role_chk or role_chk[0] != 'support':
                current_bot.answer_callback_query(call.id, "❌ Bạn không phải người hỗ trợ ticket này!", show_alert=True); conn.close(); return

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
            
            current_bot.send_message(it_id, f"🔙 Bạn đã rời khỏi nhóm hỗ trợ Ticket #{ticket_id}.")
            
            cursor.execute("SELECT user_id, role FROM active_sessions WHERE ticket_id = ?", (ticket_id,))
            for p_id, role in cursor.fetchall():
                try:
                    if role == 'customer': current_bot.send_message(p_id, f"👨‍🔧 IT hỗ trợ **{it_info[0]}** đã rời khỏi cuộc trò chuyện.", parse_mode="Markdown")
                    elif role == 'main': current_bot.send_message(p_id, f"👨‍🔧 Đồng đội **{it_info[0]}** đã rời khỏi nhóm hỗ trợ.", parse_mode="Markdown")
                except: pass
            
            current_bot.answer_callback_query(call.id, "Đã rời Ticket thành công!")

        elif action == 'abort':
            group_msg_id = parts[2] if len(parts) > 2 else None
            cursor.execute("SELECT user_id, role FROM active_sessions WHERE ticket_id = ?", (ticket_id,))
            participants = cursor.fetchall()
            cursor.execute("DELETE FROM active_sessions WHERE ticket_id = ?", (ticket_id,))
            cursor.execute('SELECT user_name, dept, issue, group_support_msg_id FROM tickets WHERE id = ?', (ticket_id,))
            res = cursor.fetchone()
            
            if group_msg_id:
                try: current_bot.delete_message(GROUP_IT_ID, group_msg_id)
                except: pass
            if res and res[3]:
                try: current_bot.delete_message(GROUP_IT_ID, res[3])
                except: pass
            
            try: current_bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            except: pass
            
            current_bot.send_message(it_id, "🔙 Bạn đã nhả Ticket thành công.")
            for p_id, role in participants:
                if role == 'customer': current_bot.send_message(p_id, "⚠️ IT hiện tại đang bận xử lý khẩn cấp, sự cố của bạn đã chuyển lại cho team!")
                elif role == 'support': current_bot.send_message(p_id, "🔙 IT Chính đã nhả Ticket.")
            
            if res:
                text_repost = f"🚨 **TICKET #{ticket_id} BỊ TRẢ LẠI**\n👤 Khách: {res[0]}\n🏢 Phòng: {res[1]}\n📝 Lỗi: {res[2]}"
                markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤝 Nhận việc", callback_data=f"claim_{ticket_id}"))
                sent_msg = current_bot.send_message(GROUP_IT_ID, text_repost, reply_markup=markup, parse_mode="Markdown")
                cursor.execute("UPDATE tickets SET it_id=NULL, it_name=NULL, support_it_ids=NULL, support_it_names=NULL, status='Mới', group_msg_id=?, it_msg_id=NULL WHERE id=?", (sent_msg.message_id, ticket_id))
                conn.commit()
                ticket_last_status[int(ticket_id)] = 'Mới'

        elif action == 'done':
            cursor.execute("SELECT role FROM active_sessions WHERE user_id = ? AND ticket_id = ?", (it_id, ticket_id))
            role_chk = cursor.fetchone()
            if not role_chk or role_chk[0] != 'main':
                current_bot.answer_callback_query(call.id, "❌ Chỉ IT Làm Chính mới được Đóng Ticket!", show_alert=True); conn.close(); return

            cursor.execute("SELECT user_id, role FROM active_sessions WHERE ticket_id = ?", (ticket_id,))
            participants = cursor.fetchall()
            cursor.execute("DELETE FROM active_sessions WHERE ticket_id = ?", (ticket_id,))

            cursor.execute("UPDATE tickets SET status = 'Hoàn thành' WHERE id = ?", (ticket_id,))
            cursor.execute('SELECT user_name, dept, issue, it_name, support_it_names, group_support_msg_id FROM tickets WHERE id = ?', (ticket_id,))
            res = cursor.fetchone()
            conn.commit()
            ticket_last_status[int(ticket_id)] = 'Hoàn thành'

            try: current_bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            except: pass

            if res and res[5]:
                try: current_bot.delete_message(GROUP_IT_ID, res[5])
                except: pass

            if len(parts) > 2 and res:
                sup_text = f"\n👨‍🔧 **Hỗ trợ:** {res[4]}" if res[4] else ""
                text_fin = f"🚨 **YÊU CẦU #{ticket_id}**\n👤 Khách: {res[0]}\n🏢 Phòng: {res[1]}\n📝 Lỗi: {res[2]}\n\n✅ **Hoàn thành**\n👨‍💻 **IT Chính:** {res[3]}{sup_text}"
                safe_edit_message(current_bot, GROUP_IT_ID, parts[2], text_fin)
            
            for p_id, role in participants:
                if role == 'main': current_bot.send_message(p_id, f"🎉 Đã đóng Ticket **#{ticket_id}**.")
                elif role == 'support': current_bot.send_message(p_id, f"🎉 Ticket **#{ticket_id}** đã được đóng bởi IT Chính.")
                elif role == 'customer':
                    current_bot.send_message(p_id, f"✅ **Sự cố của bạn đã hoàn tất.**\nVui lòng đánh giá dịch vụ:", reply_markup=get_rating_keyboard(ticket_id), parse_mode="Markdown")
                    current_bot.send_message(p_id, "👇 Báo sự cố khác:", reply_markup=get_report_keyboard())

        conn.close()

def run_bot_polling():
    global bot, is_running
    while is_running:
        try:
            if bot: bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
            time.sleep(2)  
        except:
            if is_running: time.sleep(5)

def config_watchdog():
    global bot, TOKEN, GROUP_IT_ID, TIME_OFFSET, is_running
    while is_running:
        try:
            new_token, new_group_str, new_offset = get_config_from_db()
            if not new_token or new_token == 'ĐIỀN TOKEN VÀO ĐÂY':
                time.sleep(10); continue
                
            try: new_group = int(new_group_str)
            except: time.sleep(10); continue

            TIME_OFFSET = new_offset

            if new_token != TOKEN:
                if bot: bot.stop_polling(); time.sleep(3) 
                TOKEN = new_token
                GROUP_IT_ID = new_group
                bot = telebot.TeleBot(TOKEN)
                setup_bot_handlers(bot)
                
            elif new_group != GROUP_IT_ID:
                GROUP_IT_ID = new_group
        except: pass
        time.sleep(10) 

if __name__ == '__main__':
    print("🚀 Khởi động Hệ thống Bot IT (Chống kẹt lệnh + Rời Hỗ Trợ)...")
    init_db()
    threading.Thread(target=config_watchdog, daemon=True).start()
    threading.Thread(target=auto_remind_it, daemon=True).start()
    threading.Thread(target=sync_hubs_with_db, daemon=True).start()
    run_bot_polling()