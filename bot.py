import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import threading
import time
import sys

ticket_hubs = {}  
user_to_ticket = {} 
user_states = {}  

bot = None
TOKEN = None
GROUP_IT_ID = None
TIME_OFFSET = 0  # Biến lưu trữ bù trừ thời gian (Tính bằng Giây)
is_running = True
last_reminder_msg_id = None 

def connect_db():
    return sqlite3.connect('helpdesk.db', timeout=20, check_same_thread=False)

def init_db():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, user_name TEXT, dept TEXT, issue TEXT, status TEXT, it_id INTEGER, it_name TEXT, created_at TEXT, rating INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, dept TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS it_staff (it_id INTEGER PRIMARY KEY, it_real_name TEXT, it_phone TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS departments (id INTEGER PRIMARY KEY, name TEXT UNIQUE, topic_id INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    
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
    
    cursor.execute("SELECT id, user_id, it_id, support_it_ids FROM tickets WHERE status = 'Đang xử lý'")
    for row in cursor.fetchall():
        t_id, c_id, m_id, s_ids_str = row
        s_ids = [int(x) for x in s_ids_str.split(',')] if s_ids_str else []
        ticket_hubs[t_id] = {'customer': c_id, 'main': m_id, 'supports': s_ids}
        if c_id: user_to_ticket[c_id] = t_id
        if m_id: user_to_ticket[m_id] = t_id
        for s in s_ids: user_to_ticket[s] = t_id
            
    conn.commit()
    conn.close()

# --- HÀM LẤY THỜI GIAN ĐÃ BÙ TRỪ TÍNH BẰNG GIÂY ---
def get_adjusted_time():
    return datetime.now() + timedelta(seconds=TIME_OFFSET)

# --- LUỒNG ĐỒNG BỘ RAM VỚI WEB ---
def sync_hubs_with_db():
    """Luồng đồng bộ: Nếu Ticket bị xoá hoặc đổi trạng thái trên Web, giải phóng RAM của Bot"""
    global is_running
    while is_running:
        try:
            time.sleep(5)
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id, status FROM tickets")
            db_tickets = {row[0]: row[1] for row in cursor.fetchall()}
            conn.close()

            current_ids = list(ticket_hubs.keys())
            for t_id in current_ids:
                if t_id not in db_tickets or db_tickets[t_id] != 'Đang xử lý':
                    hub = ticket_hubs.pop(t_id, None)
                    if hub:
                        user_to_ticket.pop(hub.get('customer'), None)
                        user_to_ticket.pop(hub.get('main'), None)
                        for s_id in hub.get('supports', []):
                            user_to_ticket.pop(s_id, None)
        except Exception as e:
            pass

notified_tickets = set()

def auto_remind_it():
    global bot, GROUP_IT_ID, is_running, last_reminder_msg_id
    while is_running:
        try:
            time.sleep(60) 
            if not bot or not GROUP_IT_ID:
                continue
                
            conn = connect_db()
            cursor = conn.cursor()
            # Dùng get_adjusted_time() thay vì datetime.now()
            fifteen_mins_ago = (get_adjusted_time() - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("SELECT id FROM tickets WHERE status = 'Mới' AND created_at < ?", (fifteen_mins_ago,))
            rows = cursor.fetchall()
            conn.close()
            
            to_notify = []
            for r in rows:
                ticket_id = r[0]
                if ticket_id not in notified_tickets:
                    to_notify.append(ticket_id)
                    notified_tickets.add(ticket_id) 
                    
            if to_notify:
                ids = ", ".join([f"#{tid}" for tid in to_notify])
                
                if last_reminder_msg_id:
                    try: bot.delete_message(GROUP_IT_ID, last_reminder_msg_id)
                    except: pass

                msg = bot.send_message(GROUP_IT_ID, f"📢 **THÔNG BÁO NHẮC VIỆC KHẨN CẤP!**\n\nCác sự cố {ids} đã treo hơn 15 phút mà chưa có ai tiếp nhận. Anh em IT vào kiểm tra và xử lý gấp nhé! 🔥", parse_mode="Markdown")
                last_reminder_msg_id = msg.message_id 

        except Exception as e:
            print(f"Lỗi nhắc việc: {e}")

def get_config_from_db():
    conn = connect_db()
    cursor = conn.cursor()
    token_row = cursor.execute("SELECT value FROM settings WHERE key='BOT_TOKEN'").fetchone()
    group_row = cursor.execute("SELECT value FROM settings WHERE key='GROUP_IT_ID'").fetchone()
    offset_row = cursor.execute("SELECT value FROM settings WHERE key='TIME_OFFSET'").fetchone()
    conn.close()
    
    t = token_row[0].strip() if token_row else None
    g = group_row[0].strip() if group_row else None
    o = int(offset_row[0]) if offset_row else 0
    return t, g, o

def setup_bot_handlers(current_bot):

    @current_bot.message_handler(commands=['getid'])
    def get_exact_id(message):
        # Lệnh này không bị giới hạn bởi GROUP_IT_ID, ai gõ ở đâu bot cũng báo ID ở đó
        current_bot.send_message(
            message.chat.id, 
            f"🎯 ID CHÍNH XÁC CỦA NHÓM NÀY LÀ:\n\n`{message.chat.id}`\n\n👉 Hãy copy DÃY SỐ TRÊN (bao gồm cả dấu trừ) và dán vào Web Dashboard!", 
            parse_mode="Markdown"
        )
        
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

    @current_bot.message_handler(commands=['pending'])
    def check_pending(message):
        if message.chat.id != GROUP_IT_ID: return 
        conn = connect_db(); cursor = conn.cursor()
        cursor.execute("SELECT id, user_name, dept, created_at FROM tickets WHERE status = 'Mới'")
        rows = cursor.fetchall(); conn.close()

        if not rows:
            current_bot.send_message(GROUP_IT_ID, "✅ Tuyệt vời! Hiện tại không còn sự cố nào đang chờ tiếp nhận.", message_thread_id=message.message_thread_id)
        else:
            text = "⚠️ **DANH SÁCH SỰ CỐ ĐANG CHỜ:**\n\n"
            for r in rows: text += f"🔹 **#{r[0]}** - {r[1]} - {r[2]} - *{r[3][11:16]}*\n"
            current_bot.send_message(GROUP_IT_ID, text, parse_mode="Markdown", message_thread_id=message.message_thread_id)

    @current_bot.message_handler(content_types=['new_chat_members'])
    def welcome_new_it_member(message):
        if message.chat.id != GROUP_IT_ID: return
        bot_info = current_bot.get_me()
        auth_url = f"https://t.me/{bot_info.username}?start=iam_it"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("👨‍💻 Bấm vào đây để Xác Thực IT", url=auth_url))
        
        for new_member in message.new_chat_members:
            if not new_member.is_bot: 
                user_name = new_member.first_name
                if new_member.last_name: user_name += f" {new_member.last_name}"
                text = f"👋 Chào mừng đồng đội IT mới [{user_name}](tg://user?id={new_member.id})!\n\n🚨 **QUAN TRỌNG:** Để hệ thống có thể chia việc cho bạn, bạn **BẮT BUỘC** phải nhấn vào nút bên dưới và bấm **Start** để xác thực tài khoản nhé."
                current_bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

    @current_bot.message_handler(commands=['setup_it'])
    def setup_it_group(message):
        if message.chat.id != GROUP_IT_ID: return
        auth_url = f"https://t.me/{current_bot.get_me().username}?start=iam_it"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("👨‍💻 Xác Thực IT", url=auth_url))
        current_bot.send_message(message.chat.id, "🚨 **NHÂN SỰ IT:** Bấm nút để đăng ký tên & SĐT.", reply_markup=markup, parse_mode="Markdown", message_thread_id=message.message_thread_id)

    @current_bot.message_handler(commands=['setup'])
    def setup_group(message):
        if message.chat.type == 'private': return
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🆘 Liên hệ IT (Báo sự cố)", url=f"https://t.me/{current_bot.get_me().username}"))
        current_bot.send_message(message.chat.id, f"🏢 **CỔNG TIẾP NHẬN SỰ CỐ IT CHUNG**\n\nMọi người nhấn nút bên dưới để chuyển sang chat với Bot và báo lỗi nhé.", reply_markup=markup, parse_mode="Markdown", message_thread_id=message.message_thread_id)

    @current_bot.message_handler(commands=['start'])
    def start(message):
        if message.chat.type != 'private': return
        args = message.text.split()
        conn = connect_db(); cursor = conn.cursor()
        if len(args) > 1:
            if args[1] == 'it_support': return
            if args[1] == 'iam_it': 
                user_states[message.from_user.id] = {'step': 'waiting_for_it_name'}
                current_bot.send_message(message.chat.id, "👨‍💻 **XÁC THỰC IT:** Nhập **Họ tên hiển thị** của bạn:", parse_mode="Markdown")
                conn.close(); return
            try:
                dept = bytes.fromhex(args[1]).decode('utf-8')
                cursor.execute('INSERT OR REPLACE INTO users (user_id, name, dept) VALUES (?, ?, ?)', (message.from_user.id, message.from_user.full_name, dept))
                conn.commit()
                user_states[message.from_user.id] = {'step': 'waiting_for_issue'}
                
                markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Hủy báo cáo", callback_data="cancelReport"))
                current_bot.send_message(message.chat.id, f"✅ **Hệ thống IT - {dept}** chào bạn!\n\nMời bạn mô tả lỗi tại đây.", reply_markup=markup, parse_mode="Markdown")
            except: pass
        else:
            cursor.execute('SELECT it_real_name FROM it_staff WHERE it_id = ?', (message.from_user.id,))
            is_it = cursor.fetchone()
            if is_it:
                current_bot.send_message(message.chat.id, f"👨‍💻 Chào IT **{is_it[0]}**. Tài khoản của bạn đã được xác thực.\nHãy theo dõi nhóm tổng để nhận việc nhé!", parse_mode="Markdown")
            else:
                cursor.execute('SELECT name, dept FROM users WHERE user_id = ?', (message.from_user.id,))
                user = cursor.fetchone()
                if user: 
                    current_bot.send_message(message.chat.id, f"👋 Chào mừng trở lại, **{user[0]}** - Phòng: **{user[1]}**.", reply_markup=get_report_keyboard(), parse_mode="Markdown")
                else:
                    user_states[message.from_user.id] = {'step': 'ask_name'}
                    current_bot.send_message(message.chat.id, "👋 Chào mừng bạn! Cho biết **Họ và Tên** của bạn:")
        conn.close()

    @current_bot.message_handler(content_types=['text', 'photo', 'document'])
    def handle_all_messages(message):
        if message.chat.id == GROUP_IT_ID: return 
        if message.chat.type != 'private': return
        if message.text and message.text.startswith('/'): return
        sender_id = message.chat.id
        state = user_states.get(sender_id)
        
        if state:
            if state.get('step') == 'waiting_for_it_name':
                user_states[sender_id]['it_name'], user_states[sender_id]['step'] = message.text, 'waiting_for_it_phone'
                current_bot.send_message(sender_id, f"📱 Chào **{message.text}**, nhập **Số điện thoại** của bạn:", parse_mode="Markdown")
                return
            elif state.get('step') == 'waiting_for_it_phone':
                it_name, it_phone = state.get('it_name'), message.text
                conn = connect_db(); conn.execute('INSERT OR REPLACE INTO it_staff (it_id, it_real_name, it_phone) VALUES (?, ?, ?)', (sender_id, it_name, it_phone)); conn.commit(); conn.close()
                user_states.pop(sender_id, None)
                current_bot.send_message(sender_id, f"✅ Xác thực thành công!\n👤 {it_name} - 📞 {it_phone}\nGiờ bạn có thể nhận việc.")
                return

        if sender_id in user_to_ticket:
            t_id = user_to_ticket[sender_id]
            hub = ticket_hubs.get(t_id)
            if hub:
                if sender_id == hub['customer']: prefix = "👤 **Khách:** "
                elif sender_id == hub['main']: prefix = "👨‍💻 **IT Chính:** "
                else: prefix = "👨‍🔧 **IT Hỗ trợ:** "

                recipients = [hub['customer'], hub['main']] + hub['supports']
                for r_id in set(recipients):
                    if r_id != sender_id and r_id is not None:
                        try:
                            if message.text: current_bot.send_message(r_id, f"{prefix}{message.text}", parse_mode="Markdown")
                            elif message.photo: current_bot.send_photo(r_id, message.photo[-1].file_id, caption=f"{prefix}{message.caption or ''}", parse_mode="Markdown")
                            elif message.document: current_bot.send_document(r_id, message.document.file_id, caption=f"{prefix}{message.caption or ''}", parse_mode="Markdown")
                        except: pass
            return
            
        conn = connect_db(); cursor = conn.cursor()

        cursor.execute('SELECT it_real_name FROM it_staff WHERE it_id = ?', (sender_id,))
        is_it = cursor.fetchone()
        if is_it:
            current_bot.send_message(sender_id, f"👨‍💻 Chào IT **{is_it[0]}**. Bạn hiện không xử lý sự cố nào.\nHãy chờ thông báo từ nhóm tổng nhé!", parse_mode="Markdown")
            conn.close()
            return

        cursor.execute('SELECT name, dept FROM users WHERE user_id = ?', (sender_id,))
        user = cursor.fetchone()
        
        if not user:
            if not state:
                user_states[sender_id] = {'step': 'ask_name'}
                current_bot.send_message(sender_id, "Cho biết **Họ tên** của bạn:")
            elif state['step'] == 'ask_name':
                user_states[sender_id]['name'], user_states[sender_id]['step'] = message.text, 'ask_dept'
                cursor.execute("SELECT name FROM departments")
                depts = [row[0] for row in cursor.fetchall()]
                
                if depts:
                    markup = types.InlineKeyboardMarkup(row_width=1) 
                    for d in depts: markup.add(types.InlineKeyboardButton(d, callback_data=f"seldept_{d}"))
                    current_bot.send_message(sender_id, f"Chào **{message.text}**! Vui lòng chọn **Phòng ban** của bạn ở bên dưới:", reply_markup=markup, parse_mode="Markdown")
                else:
                    current_bot.send_message(sender_id, "🏢 Vui lòng nhập tên **Phòng ban** của bạn:")
                    
            elif state['step'] == 'ask_dept':
                cursor.execute('INSERT INTO users (user_id, name, dept) VALUES (?, ?, ?)', (sender_id, state['name'], message.text))
                conn.commit(); user_states.pop(sender_id, None)
                current_bot.send_message(sender_id, "✅ Đã lưu!", reply_markup=get_report_keyboard())
            conn.close(); return

        cursor.execute("SELECT id FROM tickets WHERE user_id = ? AND status = 'Mới'", (sender_id,))
        pending_ticket = cursor.fetchone()
        if pending_ticket:
            current_bot.send_message(sender_id, f"⏳ Sự cố **#{pending_ticket[0]}** của bạn đang được đẩy lên nhóm IT.\nVui lòng chờ IT tiếp nhận trong giây lát và không nhắn thêm để tránh trôi tin nhé!", parse_mode="Markdown")
            conn.close()
            return
            
        if not state or state.get('step') != 'waiting_for_issue':
            current_bot.send_message(sender_id, "👇 Nhấn nút báo sự cố:", reply_markup=get_report_keyboard()); conn.close(); return
            
        issue_text = message.text or message.caption or "Gửi đính kèm"
        
        # --- SỬ DỤNG get_adjusted_time() ĐỂ LẤY THỜI GIAN ĐÃ BÙ TRỪ KHI TẠO TICKET ---
        cursor.execute('INSERT INTO tickets (user_id, user_name, dept, issue, status, created_at) VALUES (?, ?, ?, ?, ?, ?)', (sender_id, user[0], user[1], issue_text, 'Mới', get_adjusted_time().strftime("%Y-%m-%d %H:%M:%S")))
        ticket_id, _ = cursor.lastrowid, conn.commit(); conn.close()
        user_states.pop(sender_id, None)
        
        current_bot.send_message(sender_id, "✅ **Đã gửi IT.** Vui lòng đợi.", parse_mode="Markdown")
        
        msg_to_it = f"🚨 **YÊU CẦU MỚI!**\n🆔 Mã: #{ticket_id}\n👤 Khách: {user[0]}\n🏢 Phòng: {user[1]}\n📝 Nội dung: {issue_text}"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤝 Nhận việc (Làm chính)", callback_data=f"claim_{ticket_id}"))
        if message.content_type == 'photo': current_bot.send_photo(GROUP_IT_ID, message.photo[-1].file_id, caption=msg_to_it, reply_markup=markup, parse_mode="Markdown")
        else: current_bot.send_message(GROUP_IT_ID, msg_to_it, reply_markup=markup, parse_mode="Markdown")

    @current_bot.callback_query_handler(func=lambda call: True)
    def callback_handler(call):
        
        if call.data == 'reportIssue':
            user_states[call.from_user.id] = {'step': 'waiting_for_issue'}
            markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Hủy báo cáo", callback_data="cancelReport"))
            try:
                current_bot.edit_message_text("📝 **Mời bạn mô tả lỗi:**\n*(Hoặc nhấn nút Hủy bên dưới nếu bấm nhầm)*", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    print(f"Lỗi Telegram: {e}")
            return

        if call.data == 'cancelReport':
            user_states.pop(call.from_user.id, None)
            try:
                current_bot.edit_message_text("✅ Đã hủy thao tác báo sự cố. Bạn cần hỗ trợ gì khác không?", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_report_keyboard())
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    print(f"Lỗi Telegram: {e}")
            return

        if call.data == 'changeDept':
            conn = connect_db(); cursor = conn.cursor()
            cursor.execute('SELECT name FROM users WHERE user_id = ?', (call.from_user.id,))
            user = cursor.fetchone()
            if user:
                user_states[call.from_user.id] = {'step': 'ask_dept', 'name': user[0]}
                cursor.execute("SELECT name FROM departments")
                depts = [row[0] for row in cursor.fetchall()]
                
                if depts:
                    markup = types.InlineKeyboardMarkup(row_width=1) 
                    for d in depts: markup.add(types.InlineKeyboardButton(d, callback_data=f"seldept_{d}"))
                    current_bot.edit_message_text(f"🔄 Đang cập nhật cho **{user[0]}**\n\nMời bạn chọn **Phòng ban** mới của mình:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")
                else:
                    current_bot.edit_message_text("🏢 Vui lòng nhập tên **Phòng ban** mới của bạn:", chat_id=call.message.chat.id, message_id=call.message.message_id)
            conn.close()
            return

        if call.data.startswith('seldept_'):
            dept_name = call.data[8:]
            sender_id = call.from_user.id
            state = user_states.get(sender_id)
            if state and state.get('step') == 'ask_dept':
                conn = connect_db(); cursor = conn.cursor()
                cursor.execute('INSERT OR REPLACE INTO users (user_id, name, dept) VALUES (?, ?, ?)', (sender_id, state['name'], dept_name))
                conn.commit(); conn.close()
                user_states.pop(sender_id, None)
                
                text_success = f"✅ Đã lưu thông tin!\n👤 Tên: **{state['name']}**\n🏢 Phòng ban: **{dept_name}**\n\n👇 Nhấn nút bên dưới để báo sự cố:"
                current_bot.edit_message_text(text_success, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_report_keyboard(), parse_mode="Markdown")
            return

        parts = call.data.split('_')
        action = parts[0]; ticket_id = parts[1]
        it_id = call.from_user.id

        if action == 'rate':
            conn = connect_db(); cursor = conn.cursor()
            cursor.execute('UPDATE tickets SET rating = ? WHERE id = ?', (parts[2], ticket_id)); conn.commit(); conn.close()
            current_bot.edit_message_text(f"⭐ Đã đánh giá {parts[2]} sao!", chat_id=call.message.chat.id, message_id=call.message.message_id)
            return

        conn = connect_db(); cursor = conn.cursor()
        cursor.execute('SELECT it_real_name, it_phone FROM it_staff WHERE it_id = ?', (it_id,))
        it_info = cursor.fetchone()
        if not it_info and action in ['claim', 'join']:
            current_bot.answer_callback_query(call.id, "❌ Chưa xác thực IT!", show_alert=True); conn.close(); return

        if action == 'claim':
            if it_id in user_to_ticket:
                current_bot.answer_callback_query(call.id, "❌ BẠN ĐANG BẬN! Hãy hoàn thành Ticket hiện tại trước khi nhận thêm.", show_alert=True)
                conn.close(); return

            cursor.execute('SELECT user_id, status, user_name, dept, issue FROM tickets WHERE id = ?', (ticket_id,))
            res = cursor.fetchone()
            if not res or res[1] != 'Mới':
                current_bot.answer_callback_query(call.id, "❌ Đã có người nhận!", show_alert=True); conn.close(); return
            
            user_id = res[0]
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ Hoàn thành", callback_data=f"done_{ticket_id}_{call.message.message_id}"),
                       types.InlineKeyboardButton("🆘 Thêm người hỗ trợ", callback_data=f"asksupport_{ticket_id}_{call.message.message_id}"))
            markup.add(types.InlineKeyboardButton("🔙 Không thực hiện được (Trả lại)", callback_data=f"abort_{ticket_id}_{call.message.message_id}"))
            
            msg_to_it = f"🚀 **[LÀM CHÍNH] YÊU CẦU #{ticket_id}**\n👤 Khách: {res[2]}\n🏢 Phòng: {res[3]}\n📝 Lỗi: {res[4]}\n👉 Chat trực tiếp với khách bên dưới:"
            try: current_bot.send_message(it_id, msg_to_it, reply_markup=markup, parse_mode="Markdown")
            except: current_bot.answer_callback_query(call.id, "❌ Nhắn tin riêng với Bot trước!", show_alert=True); conn.close(); return

            cursor.execute('UPDATE tickets SET it_id = ?, it_name = ?, status = ? WHERE id = ?', (it_id, it_info[0], 'Đang xử lý', ticket_id))
            
            cursor.execute("SELECT count(*) FROM tickets WHERE status = 'Mới'")
            if cursor.fetchone()[0] == 0:
                global last_reminder_msg_id
                if last_reminder_msg_id:
                    try: current_bot.delete_message(GROUP_IT_ID, last_reminder_msg_id)
                    except: pass
                    last_reminder_msg_id = None
            
            conn.commit()

            text_proc = f"🚨 **YÊU CẦU #{ticket_id}**\n👤 Khách: {res[2]}\n🏢 Phòng: {res[3]}\n📝 Lỗi: {res[4]}\n\n⏳ **Đang xử lý**\n👨‍💻 **IT Chính:** {it_info[0]}"
            if call.message.photo: current_bot.edit_message_caption(chat_id=GROUP_IT_ID, message_id=call.message.message_id, caption=text_proc, reply_markup=None, parse_mode="Markdown")
            else: current_bot.edit_message_text(chat_id=GROUP_IT_ID, message_id=call.message.message_id, text=text_proc, reply_markup=None, parse_mode="Markdown")

            ticket_hubs[int(ticket_id)] = {'customer': user_id, 'main': it_id, 'supports': []}
            user_to_ticket[user_id] = int(ticket_id)
            user_to_ticket[it_id] = int(ticket_id)
            
            current_bot.send_message(user_id, f"👨‍💻 IT **{it_info[0]}** ({it_info[1]}) đang hỗ trợ bạn. Vui lòng giữ kết nối.", parse_mode="Markdown")
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
            hub = ticket_hubs.get(int(ticket_id))
            if not hub:
                current_bot.answer_callback_query(call.id, "❌ Ticket này đã đóng hoặc lỗi!", show_alert=True); conn.close(); return
            if it_id == hub['main']:
                current_bot.answer_callback_query(call.id, "❌ Bạn đã là người làm chính rồi!", show_alert=True); conn.close(); return
            if it_id in user_to_ticket:
                current_bot.answer_callback_query(call.id, "❌ BẠN ĐANG BẬN xử lý Ticket khác!", show_alert=True); conn.close(); return

            cursor.execute('SELECT support_it_ids, support_it_names FROM tickets WHERE id = ?', (ticket_id,))
            res = cursor.fetchone()
            s_ids = f"{res[0]},{it_id}" if res[0] else str(it_id)
            s_names = f"{res[1]}, {it_info[0]}" if res[1] else it_info[0]
            cursor.execute('UPDATE tickets SET support_it_ids = ?, support_it_names = ? WHERE id = ?', (s_ids, s_names, ticket_id))
            conn.commit()

            hub['supports'].append(it_id)
            user_to_ticket[it_id] = int(ticket_id)

            current_bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            
            try: current_bot.send_message(it_id, f"🚀 **[HỖ TRỢ] YÊU CẦU #{ticket_id}**\nĐã tham gia nhóm chat của ticket này. Bạn có thể chat ngay.")
            except: pass
            
            current_bot.send_message(hub['customer'], f"👨‍🔧 IT **{it_info[0]}** ({it_info[1]}) vừa tham gia hỗ trợ sự cố này.")
            current_bot.send_message(hub['main'], f"👨‍🔧 Đồng đội **{it_info[0]}** ({it_info[1]}) vừa vào hỗ trợ bạn.")
            current_bot.answer_callback_query(call.id, url=f"https://t.me/{(current_bot.get_me()).username}?start=it_support")

        elif action == 'abort':
            group_msg_id = parts[2] if len(parts) > 2 else None
            hub = ticket_hubs.pop(int(ticket_id), None)
            if not hub: conn.close(); return
            
            user_to_ticket.pop(hub['customer'], None)
            user_to_ticket.pop(hub['main'], None)
            for s in hub['supports']: user_to_ticket.pop(s, None)

            cursor.execute("UPDATE tickets SET it_id=NULL, it_name=NULL, support_it_ids=NULL, support_it_names=NULL, status='Mới' WHERE id=?", (ticket_id,))
            cursor.execute('SELECT user_name, dept, issue, group_support_msg_id FROM tickets WHERE id = ?', (ticket_id,))
            res = cursor.fetchone()
            conn.commit()
            
            if group_msg_id:
                try: current_bot.delete_message(GROUP_IT_ID, group_msg_id)
                except: pass

            if res and res[3]:
                try: current_bot.delete_message(GROUP_IT_ID, res[3])
                except: pass
            
            current_bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            current_bot.send_message(it_id, "🔙 Bạn đã nhả Ticket thành công.")
            current_bot.send_message(hub['customer'], "⚠️ IT hiện tại đang bận xử lý khẩn cấp, sự cố của bạn đã được chuyển lại cho team. Sẽ có IT khác tiếp nhận ngay, xin thông cảm!")
            
            if res:
                text_repost = f"🚨 **TICKET #{ticket_id} BỊ TRẢ LẠI (CẦN NGƯỜI NHẬN MỚI)**\n👤 Khách: {res[0]}\n🏢 Phòng: {res[1]}\n📝 Lỗi: {res[2]}"
                markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤝 Nhận việc", callback_data=f"claim_{ticket_id}"))
                current_bot.send_message(GROUP_IT_ID, text_repost, reply_markup=markup, parse_mode="Markdown")

        elif action == 'done':
            hub = ticket_hubs.get(int(ticket_id))
            if not hub: conn.close(); return
            if call.from_user.id != hub['main']:
                current_bot.answer_callback_query(call.id, "❌ Chỉ IT Làm Chính mới có quyền Đóng Ticket!", show_alert=True); conn.close(); return

            ticket_hubs.pop(int(ticket_id), None)
            user_to_ticket.pop(hub['customer'], None)
            user_to_ticket.pop(hub['main'], None)
            for s in hub['supports']: user_to_ticket.pop(s, None)

            cursor.execute("UPDATE tickets SET status = 'Hoàn thành' WHERE id = ?", (ticket_id,))
            cursor.execute('SELECT user_name, dept, issue, it_name, support_it_names, group_support_msg_id FROM tickets WHERE id = ?', (ticket_id,))
            res = cursor.fetchone()
            conn.commit()

            try: current_bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            except: pass

            if res and res[5]:
                try: current_bot.delete_message(GROUP_IT_ID, res[5])
                except: pass

            if len(parts) > 2 and res:
                sup_text = f"\n👨‍🔧 **Hỗ trợ:** {res[4]}" if res[4] else ""
                text_fin = f"🚨 **YÊU CẦU #{ticket_id}**\n👤 Khách: {res[0]}\n🏢 Phòng: {res[1]}\n📝 Lỗi: {res[2]}\n\n✅ **Hoàn thành**\n👨‍💻 **IT Chính:** {res[3]}{sup_text}"
                try: current_bot.edit_message_text(chat_id=GROUP_IT_ID, message_id=parts[2], text=text_fin, parse_mode="Markdown")
                except: pass
            
            current_bot.send_message(hub['main'], f"🎉 Đã đóng Ticket **#{ticket_id}**.")
            for s in hub['supports']: current_bot.send_message(s, f"🎉 Ticket **#{ticket_id}** đã được đóng bởi IT Chính.")
            
            current_bot.send_message(hub['customer'], f"✅ **Sự cố của bạn đã hoàn tất.**\nVui lòng đánh giá dịch vụ:", reply_markup=get_rating_keyboard(ticket_id), parse_mode="Markdown")
            current_bot.send_message(hub['customer'], "👇 Báo sự cố khác:", reply_markup=get_report_keyboard())

        conn.close()


def run_bot_polling():
    global bot, is_running
    while is_running:
        try:
            if bot:
                bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            if is_running:
                print(f"Lỗi Polling: {e}. Đang thử lại sau 5s...")
                time.sleep(5)

def config_watchdog():
    global bot, TOKEN, GROUP_IT_ID, TIME_OFFSET, is_running
    while is_running:
        try:
            new_token, new_group_str, new_offset = get_config_from_db()
            
            if not new_token or new_token == 'ĐIỀN TOKEN VÀO ĐÂY':
                time.sleep(10)
                continue
                
            try: 
                new_group = int(new_group_str)
            except: 
                time.sleep(10)
                continue

            # Cập nhật thời gian bù trừ
            TIME_OFFSET = new_offset

            # Nếu chưa có TOKEN (lúc mới chạy) HOẶC Token bị thay đổi -> Bắt buộc Restart Bot
            if new_token != TOKEN:
                print(f"\n🔄 Phát hiện Token mới! Đang tải lại Bot...")
                if bot:
                    bot.stop_polling()
                    time.sleep(3) 
                TOKEN = new_token
                GROUP_IT_ID = new_group
                bot = telebot.TeleBot(TOKEN)
                setup_bot_handlers(bot)
                print(f"✅ Tải Token mới thành công! Giám sát nhóm: {GROUP_IT_ID}")
                
            # Nếu Token GIỮ NGUYÊN, chỉ đổi mỗi ID Nhóm -> KHÔNG Restart Bot, chỉ cập nhật biến
            elif new_group != GROUP_IT_ID:
                GROUP_IT_ID = new_group
                print(f"🔄 Đã cập nhật ID Nhóm mới: {GROUP_IT_ID} (Bot vẫn chạy mượt mà)")

        except Exception as e:
            pass
        time.sleep(10) 

# CHẠY HỆ THỐNG
if __name__ == '__main__':
    print("🚀 Khởi động Hệ thống Bot IT Command Center (Hot-Reload Mode)...")
    init_db()
    
    watchdog_thread = threading.Thread(target=config_watchdog, daemon=True)
    watchdog_thread.start()
    
    threading.Thread(target=auto_remind_it, daemon=True).start()
    
    threading.Thread(target=sync_hubs_with_db, daemon=True).start()
    
    run_bot_polling()