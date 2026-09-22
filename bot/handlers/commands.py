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

    @current_bot.message_handler(commands=['done', 'hoanthanh', 'close'])
    def done_command(message):
        user_id = message.from_user.id
        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT it_real_name FROM it_staff WHERE it_id = ?", (user_id,))
            is_it = cursor.fetchone()
            
            target_ticket_id = None
            args = message.text.split()
            if len(args) > 1 and args[1].isdigit():
                target_ticket_id = int(args[1])
            elif message.message_thread_id:
                cursor.execute("SELECT id FROM tickets WHERE topic_id = ?", (message.message_thread_id,))
                t_row = cursor.fetchone()
                if t_row:
                    target_ticket_id = t_row[0]
            
            if not target_ticket_id:
                cursor.execute("SELECT ticket_id FROM active_sessions WHERE user_id = ? AND role = 'main' ORDER BY ticket_id DESC LIMIT 1", (user_id,))
                sess = cursor.fetchone()
                if sess:
                    target_ticket_id = sess[0]

            if not target_ticket_id:
                current_bot.reply_to(message, "❌ **Vui lòng nhập Mã Ticket!** Ví dụ: `/done 105` (Hoặc gõ `/done` trực tiếp trong Topic của Ticket)", parse_mode="Markdown")
                return

            cursor.execute("SELECT status, it_id, user_name, dept, issue, it_name, support_it_names, group_support_msg_id, group_msg_id, topic_id, user_id FROM tickets WHERE id = ?", (target_ticket_id,))
            res = cursor.fetchone()

            if not res:
                current_bot.reply_to(message, f"❌ Không tìm thấy Ticket #{target_ticket_id}!")
                return

            if res[0] == 'Hoàn thành':
                current_bot.reply_to(message, f"ℹ️ Ticket #{target_ticket_id} đã được hoàn thành trước đó.")
                return

            if not is_it and str(res[1]) != str(user_id):
                current_bot.reply_to(message, "❌ Chỉ IT mới có quyền đóng Ticket!")
                return

            cursor.execute("SELECT user_id, role, topic_id FROM active_sessions WHERE ticket_id = ?", (target_ticket_id,))
            participants = cursor.fetchall()
            cursor.execute("DELETE FROM active_sessions WHERE ticket_id = ?", (target_ticket_id,))

            from utils.helpers import get_adjusted_time, safe_edit_message
            from bot.keyboards import get_rating_keyboard
            completed_time = get_adjusted_time().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("UPDATE tickets SET status = 'Hoàn thành', completed_at = ? WHERE id = ?", (completed_time, target_ticket_id))
            conn.commit()
            bot_config.ticket_last_status[int(target_ticket_id)] = 'Hoàn thành'

            if res[7]:
                try:
                    current_bot.delete_message(bot_config.GROUP_IT_ID, res[7])
                except Exception:
                    pass
            if res[8]:
                try:
                    current_bot.unpin_chat_message(chat_id=bot_config.GROUP_IT_ID, message_id=res[8])
                except Exception:
                    pass

            if not participants and res:
                main_it_uid = res[1]
                cust_uid = res[10]
                topic_id_val = res[9]
                if main_it_uid:
                    participants.append((main_it_uid, 'main', topic_id_val))
                if cust_uid and str(cust_uid) != '0':
                    participants.append((cust_uid, 'customer', None))

            cust_name = res[2] if res else "Khách"
            for p_id, role, p_topic in participants:
                if role in ['main', 'support']:
                    target_topic = p_topic if p_topic else (res[9] if (res and role == 'main') else None)
                    if target_topic:
                        cursor.execute("SELECT workspace_group_id FROM it_staff WHERE it_id = ?", (p_id,))
                        ws_row = cursor.fetchone()
                        if ws_row and ws_row[0]:
                            try:
                                current_bot.edit_forum_topic(chat_id=ws_row[0], message_thread_id=target_topic, name=f"✅ [ĐÃ XONG] #{target_ticket_id} - {cust_name}"[:120])
                            except Exception:
                                pass
                            try:
                                current_bot.send_message(ws_row[0], f"🎉 Đã đóng Ticket #{target_ticket_id} thành công.", message_thread_id=target_topic)
                            except Exception:
                                pass
                            try:
                                current_bot.close_forum_topic(chat_id=ws_row[0], message_thread_id=target_topic)
                            except Exception:
                                pass
                    else:
                        msg = f"🎉 Đã đóng Ticket **#{target_ticket_id}**." if role == 'main' else f"🎉 Ticket **#{target_ticket_id}** đã được đóng."
                        try:
                            current_bot.send_message(p_id, msg, parse_mode="Markdown")
                        except Exception:
                            pass
                elif role == 'customer':
                    try:
                        current_bot.send_message(p_id, f"✅ **Sự cố của bạn đã hoàn tất.**\nVui lòng đánh giá dịch vụ:", reply_markup=get_rating_keyboard(target_ticket_id), parse_mode="Markdown")
                        current_bot.send_message(p_id, "👇 Báo sự cố khác:", reply_markup=get_report_keyboard())
                    except Exception:
                        pass

            if res[8]:
                sup_text = f"\n👨‍🔧 **Hỗ trợ:** {res[6]}" if res[6] else ""
                text_fin = f"🚨 **YÊU CẦU #{target_ticket_id}**\n👤 Khách: {res[2]}\n🏢 Phòng: {res[3]}\n📝 Lỗi: {res[4]}\n\n✅ **Hoàn thành**\n👨‍💻 **IT Chính:** {res[5]}{sup_text}"
                safe_edit_message(current_bot, bot_config.GROUP_IT_ID, res[8], text_fin)

            current_bot.reply_to(message, f"🎉 **Đã hoàn thành Ticket #{target_ticket_id} thành công!**", parse_mode="Markdown")
        finally:
            conn.close()

    @current_bot.message_handler(commands=['claim', 'nhan'])
    def claim_command(message):
        args = message.text.split()
        if len(args) < 2 or not args[1].isdigit():
            current_bot.reply_to(message, "❌ **Vui lòng nhập Mã Ticket!** Ví dụ: `/claim 105`", parse_mode="Markdown")
            return
        ticket_id = int(args[1])
        it_id = message.from_user.id
        
        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT it_real_name, it_phone, workspace_group_id FROM it_staff WHERE it_id = ?', (it_id,))
            it_info = cursor.fetchone()
            if not it_info:
                current_bot.reply_to(message, "❌ Bạn chưa xác thực tài khoản IT!")
                return
            
            cursor.execute("UPDATE tickets SET it_id = ?, it_name = ?, status = 'Đang xử lý' WHERE id = ? AND status = 'Mới'", (it_id, it_info[0], ticket_id))
            if cursor.rowcount == 0:
                current_bot.reply_to(message, f"❌ Ticket #{ticket_id} đã được nhận hoặc đã đóng.")
                return

            cursor.execute('SELECT user_id, user_name, dept, issue FROM tickets WHERE id = ?', (ticket_id,))
            res = cursor.fetchone()
            user_id = res[0]
            
            cursor.execute("INSERT OR REPLACE INTO active_sessions (user_id, ticket_id, role) VALUES (?, ?, 'customer')", (user_id, ticket_id))
            cursor.execute("INSERT OR REPLACE INTO active_sessions (user_id, ticket_id, role) VALUES (?, ?, 'main')", (it_id, ticket_id))
            conn.commit()
            bot_config.ticket_last_status[ticket_id] = 'Đang xử lý'

            try:
                current_bot.send_message(user_id, f"👨‍💻 IT **{it_info[0]}** đang hỗ trợ bạn. Vui lòng giữ kết nối.", parse_mode="Markdown")
            except Exception:
                pass

            current_bot.reply_to(message, f"🚀 **Đã nhận Ticket #{ticket_id} thành công!**", parse_mode="Markdown")
        finally:
            conn.close()

    @current_bot.message_handler(commands=['report', 'baoloi'])
    def report_command(message):
        if message.chat.type != 'private':
            return
        user_id = message.from_user.id
        clear_state(user_id)
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Hủy báo cáo", callback_data="cancelReport"))
        msg = current_bot.send_message(user_id, "📝 **Mời bạn mô tả lỗi:**\n*(Hoặc nhấn nút Hủy)*", reply_markup=markup, parse_mode="Markdown")
        set_state(user_id, 'waiting_for_issue', str(msg.message_id))

    @current_bot.message_handler(commands=['help', 'huongdan'])
    def help_command(message):
        text = (
            "📖 **HƯỚNG DẪN SỬ DỤNG BOT IT HELPDESK**\n\n"
            "👤 **Dành cho Khách hàng:**\n"
            "• `/start` - Khởi động lại Bot & Báo lỗi mới\n"
            "• `/report` hoặc `/baoloi` - Nhập mô tả báo sự cố khẩn cấp\n"
            "• `/giaicuu` - Reset kết nối khi gặp sự cố\n\n"
            "👨‍💻 **Dành cho Nhân sự IT:**\n"
            "• `/pending` - Xem danh sách sự cố đang chờ tiếp nhận\n"
            "• `/claim <mã_ticket>` - Nhận xử lý Ticket trực tiếp bằng câu lệnh\n"
            "• `/done <mã_ticket>` hoặc `/done` (trong Topic) - Đóng Ticket hoàn tất công việc\n"
            "• `/setworkspace` - Kết nối nhóm riêng làm việc đa nhiệm Topic\n"
            "• `/giaicuu` - Reset trạng thái tài khoản IT"
        )
        current_bot.reply_to(message, text, parse_mode="Markdown")

    @current_bot.message_handler(content_types=['pinned_message'])
    def delete_pin_system_message(message):
        try:
            current_bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass
