"""
Telegram Bot Callback Query Handler
Handles inline button clicks for ticket actions (claim, done, ask-support, join, leave, abort, department selection, ratings).
"""
from telebot import types
import config.settings as bot_config
from database.connection import connect_db
from database.repository import set_state, get_state, clear_state
from utils.helpers import get_adjusted_time, safe_edit_message, truncate_text
from bot.keyboards import get_rating_keyboard, get_report_keyboard, get_departments_keyboard

def register_callback_handlers(current_bot):

    @current_bot.callback_query_handler(func=lambda call: True)
    def callback_handler(call):
        if call.data == 'reportIssue':
            try:
                current_bot.answer_callback_query(call.id)
            except Exception:
                pass
            markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Hủy báo cáo", callback_data="cancelReport"))
            try: 
                current_bot.edit_message_text("📝 **Mời bạn mô tả lỗi:**\n*(Hoặc nhấn nút Hủy)*", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")
                set_state(call.from_user.id, 'waiting_for_issue', str(call.message.message_id))
            except Exception: 
                msg = current_bot.send_message(call.message.chat.id, "📝 **Mời bạn mô tả lỗi:**\n*(Hoặc nhấn nút Hủy)*", reply_markup=markup, parse_mode="Markdown")
                set_state(call.from_user.id, 'waiting_for_issue', str(msg.message_id))
            return

        if call.data == 'cancelReport':
            try:
                current_bot.answer_callback_query(call.id, "Đã hủy!")
            except Exception:
                pass
            clear_state(call.from_user.id)
            try:
                current_bot.edit_message_text("✅ Đã hủy.", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_report_keyboard())
            except Exception:
                current_bot.send_message(call.message.chat.id, "✅ Đã hủy.", reply_markup=get_report_keyboard())
            return

        if call.data == 'changeDept':
            try:
                current_bot.answer_callback_query(call.id)
            except Exception:
                pass
            conn = connect_db()
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT name FROM users WHERE user_id = ?', (call.from_user.id,))
                user = cursor.fetchone()
                if user:
                    set_state(call.from_user.id, 'ask_dept', user[0])
                    
                    cursor.execute("SELECT id, name FROM departments ORDER BY name ASC")
                    depts = cursor.fetchall()
                    if depts:
                        markup = get_departments_keyboard(depts, row_width=2)
                        try:
                            current_bot.edit_message_text(f"🔄 Đang cập nhật cho **{user[0]}**\nMời bạn chọn **Phòng ban** mới:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")
                        except Exception:
                            current_bot.send_message(call.message.chat.id, f"🔄 Đang cập nhật cho **{user[0]}**\nMời bạn chọn **Phòng ban** mới:", reply_markup=markup, parse_mode="Markdown")
                    else:
                        try:
                            current_bot.edit_message_text("🏢 Vui lòng nhập tên **Phòng ban** mới của bạn:", chat_id=call.message.chat.id, message_id=call.message.message_id)
                        except Exception:
                            current_bot.send_message(call.message.chat.id, "🏢 Vui lòng nhập tên **Phòng ban** mới của bạn:")
            finally:
                conn.close()
            return

        if call.data.startswith('seldept_'):
            try:
                current_bot.answer_callback_query(call.id, "Đã chọn phòng ban!")
            except Exception:
                pass
            dept_id = call.data[8:]
            sender_id = call.from_user.id
            step, temp_data = get_state(sender_id)
            if step == 'ask_dept':
                conn = connect_db()
                cursor = conn.cursor()
                try:
                    cursor.execute("SELECT name FROM departments WHERE id = ?", (dept_id,))
                    d_row = cursor.fetchone()
                    if d_row:
                        dept_name = d_row[0]
                        user_name = temp_data if (temp_data and temp_data != 'None') else (call.from_user.full_name or f"Khách #{sender_id}")
                        cursor.execute('INSERT OR REPLACE INTO users (user_id, name, dept) VALUES (?, ?, ?)', (sender_id, user_name, dept_name))
                        conn.commit()
                        clear_state(sender_id)
                        current_bot.edit_message_text(f"✅ Đã lưu thông tin!\n👤 Tên: **{user_name}**\n🏢 Phòng ban: **{dept_name}**", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_report_keyboard(), parse_mode="Markdown")
                finally:
                    conn.close()
            return

        parts = call.data.split('_')
        action, ticket_id = parts[0], parts[1]
        it_id = call.from_user.id

        if action == 'rate':
            try:
                current_bot.answer_callback_query(call.id, "Cảm ơn bạn đã đánh giá!")
            except Exception:
                pass
            conn = connect_db()
            cursor = conn.cursor()
            try:
                cursor.execute('UPDATE tickets SET rating = ? WHERE id = ?', (parts[2], ticket_id))
                conn.commit()
            finally:
                conn.close()
            try:
                current_bot.edit_message_text(f"⭐ Đã đánh giá {parts[2]} sao!", chat_id=call.message.chat.id, message_id=call.message.message_id)
            except Exception:
                pass
            return

        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT it_real_name, it_phone, workspace_group_id FROM it_staff WHERE it_id = ?', (it_id,))
            it_info = cursor.fetchone()
            if not it_info and action in ['claim', 'join', 'leave']:
                try:
                    current_bot.answer_callback_query(call.id, "❌ Chưa xác thực IT!", show_alert=True)
                except Exception:
                    pass
                return

            if action == 'claim':
                workspace_id = it_info[2] if it_info and len(it_info) > 2 and it_info[2] else None
                
                if not workspace_id:
                    cursor.execute("SELECT ticket_id FROM active_sessions WHERE user_id = ?", (it_id,))
                    if cursor.fetchone():
                        try:
                            current_bot.answer_callback_query(call.id, "❌ BẠN ĐANG BẬN! Hãy tạo Nhóm Workspace riêng và gõ /setworkspace để nhận nhiều Ticket cùng lúc!", show_alert=True)
                        except Exception:
                            pass
                        return

                cursor.execute("UPDATE tickets SET it_id = ?, it_name = ?, status = 'Đang xử lý' WHERE id = ? AND status = 'Mới'", (it_id, it_info[0], ticket_id))
                if cursor.rowcount == 0:
                    try:
                        current_bot.answer_callback_query(call.id, "❌ Chậm tay! Đã có người nhận hoặc Ticket bị hủy.", show_alert=True)
                    except Exception:
                        pass
                    return
                
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
                        
                        msg_to_it = f"🚀 **[LÀM CHÍNH] YÊU CẦU #{ticket_id}**\n👤 Khách: {res[1]}\n🏢 Phòng: {res[2]}\n📝 Lỗi: {truncate_text(res[3], 3500)}\n👉 Chat trực tiếp với khách bên dưới:"
                        try:
                            sent_it_msg = current_bot.send_message(workspace_id, msg_to_it, reply_markup=markup, parse_mode="Markdown", message_thread_id=topic_id)
                        except Exception:
                            sent_it_msg = current_bot.send_message(workspace_id, msg_to_it.replace("**", "").replace("*", "").replace("`", "").replace("_", ""), reply_markup=markup, message_thread_id=topic_id)
                        
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
                        msg_to_it = f"🚀 **[LÀM CHÍNH] YÊU CẦU #{ticket_id}**\n👤 Khách: {res[1]}\n🏢 Phòng: {res[2]}\n📝 Lỗi: {truncate_text(res[3], 3500)}\n👉 Chat trực tiếp với khách bên dưới:"
                        try:
                            sent_it_msg = current_bot.send_message(it_id, msg_to_it, reply_markup=markup, parse_mode="Markdown")
                        except Exception:
                            sent_it_msg = current_bot.send_message(it_id, msg_to_it.replace("**", "").replace("*", "").replace("`", "").replace("_", ""), reply_markup=markup)
                    except Exception:
                        cursor.execute("UPDATE tickets SET it_id = NULL, it_name = NULL, status = 'Mới' WHERE id = ?", (ticket_id,))
                        conn.commit()
                        try:
                            current_bot.answer_callback_query(call.id, "❌ Nhắn tin riêng với Bot hoặc gõ /setworkspace trong nhóm riêng trước!", show_alert=True)
                        except Exception:
                            pass
                        return

                it_msg_val = sent_it_msg.message_id if sent_it_msg else None
                cursor.execute('UPDATE tickets SET group_msg_id = ?, it_msg_id = ?, topic_id = ? WHERE id = ?', (call.message.message_id, it_msg_val, topic_id, ticket_id))
                
                cursor.execute("SELECT count(*) FROM tickets WHERE status = 'Mới'")
                if cursor.fetchone()[0] == 0:
                    if bot_config.last_reminder_msg_id:
                        try:
                            current_bot.delete_message(bot_config.GROUP_IT_ID, bot_config.last_reminder_msg_id)
                        except Exception:
                            pass
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
                
                try:
                    current_bot.send_message(user_id, f"👨‍💻 IT **{it_info[0]}** đang hỗ trợ bạn. Vui lòng giữ kết nối.", parse_mode="Markdown")
                except Exception:
                    pass
                try:
                    current_bot.answer_callback_query(call.id, f"✅ Đã nhận việc!")
                except Exception:
                    pass

            elif action == 'asksupport':
                try:
                    current_bot.answer_callback_query(call.id, "Đã gửi yêu cầu hỗ trợ vào nhóm IT!")
                except Exception:
                    pass
                markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤝 Tham gia hỗ trợ", callback_data=f"join_{ticket_id}"))
                cursor.execute('SELECT user_name, dept, issue, it_name FROM tickets WHERE id = ?', (ticket_id,))
                res = cursor.fetchone()
                if res:
                    text_help = f"🚨 **YÊU CẦU #{ticket_id} ĐANG CẦN SUPPORT** 🆘\n👤 Khách: {res[0]}\n🏢 Phòng: {res[1]}\n📝 Lỗi: {truncate_text(res[2], 3000)}\n\n👨‍💻 **IT Chính:** {res[3]} đang cần đồng đội hỗ trợ ca này!"
                    try:
                        sent_msg = current_bot.send_message(bot_config.GROUP_IT_ID, text_help, reply_markup=markup, parse_mode="Markdown")
                    except Exception:
                        sent_msg = current_bot.send_message(bot_config.GROUP_IT_ID, text_help.replace("**", "").replace("*", "").replace("`", "").replace("_", ""), reply_markup=markup)
                    cursor.execute('UPDATE tickets SET group_support_msg_id = ? WHERE id = ?', (sent_msg.message_id, ticket_id))
                    conn.commit()

            elif action == 'join':
                cursor.execute("SELECT role FROM active_sessions WHERE user_id = ? AND ticket_id = ?", (it_id, ticket_id))
                role_exist = cursor.fetchone()
                if role_exist:
                    msg_alert = "❌ Bạn đang là IT Chính của Ticket này rồi!" if role_exist[0] == 'main' else "❌ Bạn đã ở trong Ticket này rồi!"
                    try:
                        current_bot.answer_callback_query(call.id, msg_alert, show_alert=True)
                    except Exception:
                        pass
                    return
                    
                workspace_id = it_info[2] if it_info and len(it_info) > 2 and it_info[2] else None
                if not workspace_id:
                    cursor.execute("SELECT ticket_id FROM active_sessions WHERE user_id = ?", (it_id,))
                    if cursor.fetchone():
                        try:
                            current_bot.answer_callback_query(call.id, "❌ BẠN ĐANG BẬN xử lý Ticket khác! Hãy tạo Nhóm Workspace riêng để làm việc đa nhiệm.", show_alert=True)
                        except Exception:
                            pass
                        return

                cursor.execute('SELECT support_it_ids, support_it_names, user_name FROM tickets WHERE id = ?', (ticket_id,))
                res = cursor.fetchone()
                if not res:
                    try:
                        current_bot.answer_callback_query(call.id, "❌ Ticket không tồn tại!", show_alert=True)
                    except Exception:
                        pass
                    return
                
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
                    try:
                        current_bot.answer_callback_query(call.id, "❌ Có người khác vừa bấm, vui lòng bấm lại!", show_alert=True)
                    except Exception:
                        pass
                    return
                
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
                    try:
                        current_bot.send_message(it_id, f"🚀 **[HỖ TRỢ] YÊU CẦU #{ticket_id}**\nĐã tham gia nhóm chat của ticket này. Bạn có thể chat ngay.", reply_markup=markup_leave, parse_mode="Markdown")
                    except Exception:
                        pass
                
                cursor.execute("INSERT OR REPLACE INTO active_sessions (user_id, ticket_id, role, topic_id) VALUES (?, ?, 'support', ?)", (it_id, ticket_id, topic_id))
                conn.commit()

                try:
                    current_bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
                except Exception:
                    pass

                cursor.execute("SELECT user_id, role, topic_id FROM active_sessions WHERE ticket_id = ?", (ticket_id,))
                for p_id, role, p_topic in cursor.fetchall():
                    try:
                        if role == 'customer':
                            current_bot.send_message(p_id, f"👨‍🔧 IT **{it_info[0]}** vừa tham gia hỗ trợ.", parse_mode="Markdown")
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
                    except Exception:
                        pass
                
                try:
                    current_bot.answer_callback_query(call.id, "✅ Đã tham gia hỗ trợ Ticket này!")
                except Exception:
                    pass

            elif action == 'leave':
                cursor.execute("SELECT role, topic_id FROM active_sessions WHERE user_id = ? AND ticket_id = ?", (it_id, ticket_id))
                role_chk = cursor.fetchone()
                if not role_chk or role_chk[0] != 'support':
                    try:
                        current_bot.answer_callback_query(call.id, "❌ Bạn không phải người hỗ trợ ticket này!", show_alert=True)
                    except Exception:
                        pass
                    return

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

                try:
                    current_bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
                except Exception:
                    pass
                
                if topic_id and it_info[2]:
                    try:
                        current_bot.edit_forum_topic(chat_id=it_info[2], message_thread_id=topic_id, name=f"🏃‍♂️ [ĐÃ RỜI] #{ticket_id}"[:120])
                    except Exception:
                        pass
                    try:
                        current_bot.send_message(it_info[2], f"🔙 Bạn đã rời khỏi nhóm hỗ trợ Ticket #{ticket_id}.", message_thread_id=topic_id)
                    except Exception:
                        pass
                    try:
                        current_bot.close_forum_topic(chat_id=it_info[2], message_thread_id=topic_id)
                    except Exception:
                        pass
                else:
                    try:
                        current_bot.send_message(it_id, f"🔙 Bạn đã rời khỏi nhóm hỗ trợ Ticket #{ticket_id}.")
                    except Exception:
                        pass
                
                cursor.execute("SELECT user_id, role, topic_id FROM active_sessions WHERE ticket_id = ?", (ticket_id,))
                for p_id, role, p_topic in cursor.fetchall():
                    try:
                        if role == 'customer':
                            current_bot.send_message(p_id, f"👨‍🔧 IT hỗ trợ **{it_info[0]}** đã rời khỏi cuộc trò chuyện.", parse_mode="Markdown")
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
                    except Exception:
                        pass
                
                try:
                    current_bot.answer_callback_query(call.id, "Đã rời Ticket thành công!")
                except Exception:
                    pass

            elif action == 'abort':
                group_msg_id = parts[2] if len(parts) > 2 else None
                cursor.execute("SELECT user_id, role, topic_id FROM active_sessions WHERE ticket_id = ?", (ticket_id,))
                participants = cursor.fetchall()
                cursor.execute("DELETE FROM active_sessions WHERE ticket_id = ?", (ticket_id,))
                cursor.execute('SELECT user_name, dept, issue, group_support_msg_id, topic_id, it_id, group_msg_id FROM tickets WHERE id = ?', (ticket_id,))
                res = cursor.fetchone()
                
                if group_msg_id:
                    try:
                        current_bot.delete_message(bot_config.GROUP_IT_ID, group_msg_id)
                    except Exception:
                        pass
                if res and res[3]:
                    try:
                        current_bot.delete_message(bot_config.GROUP_IT_ID, res[3])
                    except Exception:
                        pass
                
                try:
                    current_bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
                except Exception:
                    pass
                
                for p_id, role, p_topic in participants:
                    if role in ['main', 'support']:
                        if p_topic:
                            cursor.execute("SELECT workspace_group_id FROM it_staff WHERE it_id = ?", (p_id,))
                            ws_row = cursor.fetchone()
                            if ws_row and ws_row[0]:
                                name_prefix = "❌ [TRẢ LẠI]" if role == 'main' else "🛑 [HỦY]"
                                try:
                                    current_bot.edit_forum_topic(chat_id=ws_row[0], message_thread_id=p_topic, name=f"{name_prefix} #{ticket_id} - {res[0] if res else ''}"[:120])
                                except Exception:
                                    pass
                                try:
                                    current_bot.send_message(ws_row[0], "🔙 Ticket đã bị nhả/hủy.", message_thread_id=p_topic)
                                except Exception:
                                    pass
                                try:
                                    current_bot.close_forum_topic(chat_id=ws_row[0], message_thread_id=p_topic)
                                except Exception:
                                    pass
                        else:
                            try:
                                current_bot.send_message(p_id, "🔙 Bạn đã nhả/rời Ticket thành công.")
                            except Exception:
                                pass
                    elif role == 'customer':
                        try:
                            current_bot.send_message(p_id, "⚠️ IT hiện tại đang bận xử lý khẩn cấp, sự cố của bạn đã chuyển lại cho team!")
                        except Exception:
                            pass
                
                try:
                    current_bot.answer_callback_query(call.id, "Đã nhả Ticket thành công!")
                except Exception:
                    pass
                
                if res:
                    text_repost = f"🚨 **TICKET #{ticket_id} BỊ TRẢ LẠI**\n👤 Khách: {res[0]}\n🏢 Phòng: {res[1]}\n📝 Lỗi: {truncate_text(res[2], 3000)}"
                    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤝 Nhận việc", callback_data=f"claim_{ticket_id}"))
                    try:
                        sent_msg = current_bot.send_message(bot_config.GROUP_IT_ID, text_repost, reply_markup=markup, parse_mode="Markdown")
                    except Exception:
                        sent_msg = current_bot.send_message(bot_config.GROUP_IT_ID, text_repost.replace("**", "").replace("*", "").replace("`", "").replace("_", ""), reply_markup=markup)
                    try:
                        current_bot.pin_chat_message(chat_id=bot_config.GROUP_IT_ID, message_id=sent_msg.message_id, disable_notification=True)
                    except Exception:
                        pass
                    cursor.execute("UPDATE tickets SET it_id=NULL, it_name=NULL, support_it_ids=NULL, support_it_names=NULL, status='Mới', group_msg_id=?, it_msg_id=NULL, topic_id=NULL WHERE id=?", (sent_msg.message_id, ticket_id))
                    conn.commit()
                    bot_config.ticket_last_status[int(ticket_id)] = 'Mới'

            elif action == 'done':
                cursor.execute("SELECT status, it_id, user_name, dept, issue, it_name, support_it_names, group_support_msg_id, group_msg_id, topic_id, user_id FROM tickets WHERE id = ?", (ticket_id,))
                res = cursor.fetchone()
                
                if not res:
                    try:
                        current_bot.answer_callback_query(call.id, "❌ Không tìm thấy Ticket!", show_alert=True)
                    except Exception:
                        current_bot.send_message(call.message.chat.id, "❌ Không tìm thấy Ticket!")
                    return

                ticket_status, main_it_id = res[0], res[1]
                if ticket_status == 'Hoàn thành':
                    try:
                        current_bot.answer_callback_query(call.id, "ℹ️ Ticket này đã hoàn thành trước đó!", show_alert=True)
                    except Exception:
                        current_bot.send_message(call.message.chat.id, f"ℹ️ Ticket #{ticket_id} đã hoàn thành trước đó.")
                    return

                cursor.execute("SELECT role FROM active_sessions WHERE user_id = ? AND ticket_id = ?", (it_id, ticket_id))
                role_chk = cursor.fetchone()
                
                is_authorized = False
                if role_chk and role_chk[0] == 'main':
                    is_authorized = True
                elif main_it_id and str(main_it_id) == str(it_id):
                    is_authorized = True
                else:
                    cursor.execute("SELECT it_real_name FROM it_staff WHERE it_id = ?", (it_id,))
                    if cursor.fetchone():
                        is_authorized = True

                if not is_authorized:
                    try:
                        current_bot.answer_callback_query(call.id, "❌ Chỉ IT mới được Đóng Ticket!", show_alert=True)
                    except Exception:
                        current_bot.send_message(call.message.chat.id, "❌ Chỉ IT mới được Đóng Ticket!")
                    return

                cursor.execute("SELECT user_id, role, topic_id FROM active_sessions WHERE ticket_id = ?", (ticket_id,))
                participants = cursor.fetchall()
                cursor.execute("DELETE FROM active_sessions WHERE ticket_id = ?", (ticket_id,))

                completed_time = get_adjusted_time().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("UPDATE tickets SET status = 'Hoàn thành', completed_at = ? WHERE id = ?", (completed_time, ticket_id))
                conn.commit()
                bot_config.ticket_last_status[int(ticket_id)] = 'Hoàn thành'

                try:
                    current_bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
                except Exception:
                    pass

                if res and res[7]: 
                    try:
                        current_bot.delete_message(bot_config.GROUP_IT_ID, res[7])
                    except Exception:
                        pass
                
                if res and res[8]: 
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
                                    current_bot.edit_forum_topic(chat_id=ws_row[0], message_thread_id=target_topic, name=f"✅ [ĐÃ XONG] #{ticket_id} - {cust_name}"[:120])
                                except Exception:
                                    pass
                                try:
                                    current_bot.send_message(ws_row[0], f"🎉 Đã đóng Ticket #{ticket_id} thành công.", message_thread_id=target_topic)
                                except Exception:
                                    pass
                                try:
                                    current_bot.close_forum_topic(chat_id=ws_row[0], message_thread_id=target_topic)
                                except Exception:
                                    pass
                        else:
                            msg = f"🎉 Đã đóng Ticket **#{ticket_id}**." if role == 'main' else f"🎉 Ticket **#{ticket_id}** đã được đóng bởi IT."
                            try:
                                current_bot.send_message(p_id, msg)
                            except Exception:
                                pass
                    elif role == 'customer':
                        try:
                            current_bot.send_message(p_id, f"✅ **Sự cố của bạn đã hoàn tất.**\nVui lòng đánh giá dịch vụ:", reply_markup=get_rating_keyboard(ticket_id), parse_mode="Markdown")
                            current_bot.send_message(p_id, "👇 Báo sự cố khác:", reply_markup=get_report_keyboard())
                        except Exception:
                            pass
                        
                try:
                    current_bot.answer_callback_query(call.id, "✅ Đã đóng Ticket!")
                except Exception:
                    try:
                        current_bot.send_message(call.message.chat.id, f"✅ **Đã hoàn thành Ticket #{ticket_id}!**")
                    except Exception:
                        pass

                g_msg_id = res[8] if res and res[8] else (int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None)
                if g_msg_id and res:
                    sup_text = f"\n👨‍🔧 **Hỗ trợ:** {res[6]}" if res[6] else ""
                    text_fin = f"🚨 **YÊU CẦU #{ticket_id}**\n👤 Khách: {res[2]}\n🏢 Phòng: {res[3]}\n📝 Lỗi: {res[4]}\n\n✅ **Hoàn thành**\n👨‍💻 **IT Chính:** {res[5]}{sup_text}"
                    safe_edit_message(current_bot, bot_config.GROUP_IT_ID, g_msg_id, text_fin)

        finally:
            conn.close()
