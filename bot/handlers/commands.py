"""
Telegram Bot Command Handlers
Handles /start, /setworkspace, /giaicuu, /getid, /pending, /setup, /setup_it, and system pin message deletion.
"""
from telebot import types
import config.settings as bot_config
from database.connection import connect_db
from database.repository import set_state, clear_state
from bot.keyboards import get_report_keyboard

def get_bot_username(current_bot):
    try:
        me = current_bot.get_me()
        return me.username if me else ""
    except Exception:
        return ""

def register_command_handlers(current_bot):

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
        if message.chat.type != 'private':
            return
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
        if message.chat.id != bot_config.GROUP_IT_ID:
            return 
        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, user_name, dept, created_at FROM tickets WHERE status = 'Mới'")
            rows = cursor.fetchall()
        finally:
            conn.close()

        if not rows:
            current_bot.send_message(bot_config.GROUP_IT_ID, "✅ Không còn sự cố nào đang chờ tiếp nhận.")
        else:
            text = "⚠️ **DANH SÁCH SỰ CỐ ĐANG CHỜ:**\n\n"
            for r in rows:
                text += f"🔹 **#{r[0]}** - {r[1]} - {r[2]} - *{r[3][11:16]}*\n"
            current_bot.send_message(bot_config.GROUP_IT_ID, text, parse_mode="Markdown")

    @current_bot.message_handler(content_types=['new_chat_members'])
    def welcome_new_it_member(message):
        if message.chat.id != bot_config.GROUP_IT_ID:
            return
        bot_uname = get_bot_username(current_bot)
        auth_url = f"https://t.me/{bot_uname}?start=iam_it" if bot_uname else "https://t.me"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("👨‍💻 Bấm vào đây để Xác Thực IT", url=auth_url))
        for new_member in message.new_chat_members:
            if not new_member.is_bot: 
                user_name = new_member.first_name + (f" {new_member.last_name}" if new_member.last_name else "")
                text = f"👋 Chào mừng đồng đội mới [{user_name}](tg://user?id={new_member.id})!\n\n🚨 Hãy nhấn nút bên dưới và bấm **Start** xác thực."
                current_bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

    @current_bot.message_handler(commands=['setup_it'])
    def setup_it_group(message):
        if message.chat.id != bot_config.GROUP_IT_ID:
            return
        bot_uname = get_bot_username(current_bot)
        auth_url = f"https://t.me/{bot_uname}?start=iam_it" if bot_uname else "https://t.me"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("👨‍💻 Xác Thực IT", url=auth_url))
        current_bot.send_message(message.chat.id, "🚨 **NHÂN SỰ IT:** Bấm nút để đăng ký tên & SĐT.", reply_markup=markup, parse_mode="Markdown")

    @current_bot.message_handler(commands=['setup'])
    def setup_group(message):
        if message.chat.type == 'private':
            return
        bot_uname = get_bot_username(current_bot)
        auth_url = f"https://t.me/{bot_uname}" if bot_uname else "https://t.me"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🆘 Liên hệ IT (Báo sự cố)", url=auth_url))
        current_bot.send_message(message.chat.id, f"🏢 **CỔNG TIẾP NHẬN SỰ CỐ IT CHUNG**\n\nNhấn nút bên dưới để báo lỗi nhé.", reply_markup=markup, parse_mode="Markdown")

    @current_bot.message_handler(commands=['start'])
    def start(message):
        if message.chat.type != 'private':
            return
        args = message.text.split()
        conn = connect_db()
        try:
            cursor = conn.cursor()
            if len(args) > 1:
                if args[1] == 'it_support':
                    return
                if args[1] == 'iam_it': 
                    clear_state(message.from_user.id)
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
                except Exception:
                    pass
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
        try:
            current_bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass
