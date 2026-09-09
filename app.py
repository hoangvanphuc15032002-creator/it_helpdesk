from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_file
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
import requests
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'Sieu_Bao_Mat_Helpdesk_2026')

def get_db_connection():
    conn = sqlite3.connect('helpdesk.db', timeout=30, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
    except:
        pass
    conn.row_factory = sqlite3.Row
    return conn

def init_web_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    try: cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    except: pass
    cursor.execute('CREATE TABLE IF NOT EXISTS web_admins (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)')
    
    cursor.execute('CREATE TABLE IF NOT EXISTS departments (id INTEGER PRIMARY KEY, name TEXT UNIQUE, topic_id INTEGER)')
    
    cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')

    offset_exist = cursor.execute("SELECT * FROM settings WHERE key='TIME_OFFSET'").fetchone()
    if not offset_exist: cursor.execute("INSERT INTO settings (key, value) VALUES ('TIME_OFFSET', '0')")

    try: cursor.execute('ALTER TABLE tickets ADD COLUMN rating INTEGER')
    except: pass
    try: cursor.execute('ALTER TABLE it_staff ADD COLUMN it_phone TEXT')
    except: pass
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN support_it_ids TEXT')
    except: pass 
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN support_it_names TEXT')
    except: pass 
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN completed_at TEXT')
    except: pass

    admin_exist = cursor.execute("SELECT * FROM web_admins WHERE username='admin'").fetchone()
    if not admin_exist: cursor.execute("INSERT INTO web_admins (username, password, role) VALUES ('admin', ?, 'superadmin')", (generate_password_hash('123456'),))
    
    # Auto migrate any existing plain text admin passwords to hashed passwords
    admins = cursor.execute("SELECT id, password FROM web_admins").fetchall()
    for row in admins:
        pwd = row['password']
        if pwd and not (pwd.startswith('scrypt:') or pwd.startswith('pbkdf2:')):
            hashed_pwd = generate_password_hash(pwd)
            cursor.execute("UPDATE web_admins SET password = ? WHERE id = ?", (hashed_pwd, row['id']))
    
    token_exist = cursor.execute("SELECT * FROM settings WHERE key='BOT_TOKEN'").fetchone()
    if not token_exist: cursor.execute("INSERT INTO settings (key, value) VALUES ('BOT_TOKEN', 'ĐIỀN TOKEN VÀO ĐÂY')")
    
    group_exist = cursor.execute("SELECT * FROM settings WHERE key='GROUP_IT_ID'").fetchone()
    if not group_exist: cursor.execute("INSERT INTO settings (key, value) VALUES ('GROUP_IT_ID', 'ĐIỀN ID NHÓM VÀO ĐÂY')")

    conn.commit()
    conn.close()

init_web_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form['username'], request.form['password']
        conn = get_db_connection()
        
        cursor = conn.cursor()
        admin_exist = cursor.execute("SELECT * FROM web_admins WHERE username='admin'").fetchone()
        if not admin_exist:
            cursor.execute("INSERT OR IGNORE INTO web_admins (username, password, role) VALUES ('admin', ?, 'superadmin')", (generate_password_hash('123456'),))
            conn.commit()
            
        admin = conn.execute("SELECT * FROM web_admins WHERE username=?", (u,)).fetchone()
        is_valid = False
        if admin:
            db_pwd = admin['password']
            if check_password_hash(db_pwd, p):
                is_valid = True
            elif db_pwd == p:
                is_valid = True
                hashed = generate_password_hash(p)
                conn.execute("UPDATE web_admins SET password=? WHERE id=?", (hashed, admin['id']))
                conn.commit()
                
        conn.close()
        if is_valid:
            session.update({'logged_in': True, 'username': admin['username'], 'role': admin['role']})
            return redirect(url_for('admin_dashboard'))
        return "<div style='text-align: center; margin-top: 50px; font-family: sans-serif;'>❌ Sai tài khoản hoặc mật khẩu! <br><br><a href='/login' style='padding: 10px 20px; background: #ef4444; color: white; text-decoration: none; border-radius: 8px;'>Thử lại</a></div>"
            
    return '''
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <title>Đăng nhập - IT Helpdesk Command Center</title>
            <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><defs><linearGradient id='g' x1='0%25' y1='0%25' x2='100%25' y2='100%25'><stop offset='0%25' stop-color='%2310b981'/><stop offset='100%25' stop-color='%23059669'/></linearGradient></defs><rect width='100' height='100' rx='28' fill='url(%23g)'/><path d='M30 46 C30 30 70 30 70 46 L70 58 A10 10 0 0 1 60 68 L50 68 C44 68 40 64 40 58' stroke='white' stroke-width='7' fill='none' stroke-linecap='round'/><rect x='22' y='42' width='14' height='22' rx='6' fill='white'/><rect x='64' y='42' width='14' height='22' rx='6' fill='white'/><circle cx='40' cy='58' r='4' fill='%23a3e635'/></svg>">
        </head>
        <body style="margin: 0; background: #f8fafc; font-family: sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh;">
            <div style="width: 100%; max-width: 400px; text-align: center; background: #fff; padding: 40px; border-radius: 20px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05), 0 8px 10px -6px rgba(0,0,0,0.01); border: 1px solid #e2e8f0;">
                <div style="width: 56px; height: 56px; background: linear-gradient(135deg, #10b981, #059669); border-radius: 16px; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center; box-shadow: 0 10px 20px rgba(16, 185, 129, 0.3);">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 012.121-14.85"></path>
                    </svg>
                </div>
                <h2 style="color: #0f172a; font-size: 22px; font-weight: 800; margin: 0 0 6px; tracking-tight: -0.5px;">IT HELPDESK</h2>
                <p style="color: #64748b; font-size: 13px; margin: 0 0 28px; font-weight: 500;">Đăng nhập vào Hệ thống Quản trị Command Center</p>
                <form method="post">
                    <p style="margin: 0 0 16px;"><input type="text" name="username" placeholder="Tài khoản Admin" required style="padding: 14px 16px; width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 12px; font-size: 14px; outline: none; transition: border 0.2s;"></p>
                    <p style="margin: 0 0 24px;"><input type="password" name="password" placeholder="Mật khẩu" required style="padding: 14px 16px; width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 12px; font-size: 14px; outline: none; transition: border 0.2s;"></p>
                    <button type="submit" style="padding: 14px 24px; background: #059669; color: white; border: none; border-radius: 12px; cursor: pointer; width: 100%; font-weight: 700; font-size: 15px; box-shadow: 0 4px 12px rgba(5, 150, 105, 0.3);">Đăng nhập ngay</button>
                </form>
            </div>
        </body>
        </html>
    '''

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@app.route('/admin')
@login_required
def admin_dashboard():
    conn = get_db_connection()
    tickets = [dict(r) for r in conn.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT 1000").fetchall()]
    depts = conn.execute("SELECT * FROM departments ORDER BY id DESC").fetchall()
    users = conn.execute("SELECT * FROM users ORDER BY user_id DESC").fetchall()
    it_staff_rows = conn.execute("SELECT * FROM it_staff").fetchall()
    it_staff = [dict(r) for r in it_staff_rows]
    admins = conn.execute("SELECT id, username, role FROM web_admins ORDER BY id ASC").fetchall()
    
    bot_token = conn.execute("SELECT value FROM settings WHERE key='BOT_TOKEN'").fetchone()
    group_id = conn.execute("SELECT value FROM settings WHERE key='GROUP_IT_ID'").fetchone()
    
    time_offset_row = conn.execute("SELECT value FROM settings WHERE key='TIME_OFFSET'").fetchone()

    token_val = bot_token['value'] if bot_token else ""
    group_val = group_id['value'] if group_id else ""
    offset_sec = int(time_offset_row['value']) if time_offset_row else 0

    bot_time = datetime.now() + timedelta(seconds=offset_sec)
    bot_time_str = bot_time.strftime('%Y-%m-%dT%H:%M')
    bot_time_parts = {
        'year': bot_time.year, 'month': bot_time.month - 1, 'day': bot_time.day,
        'hour': bot_time.hour, 'minute': bot_time.minute, 'second': bot_time.second
    }

    conn.close()
    
    return render_template('admin.html', 
                           tickets_json=json.dumps(tickets), 
                           departments_json=json.dumps([r['name'] for r in depts]), 
                           it_staff_json=json.dumps(it_staff),
                           depts=depts, users=users, it_staff=it_staff, admins=admins,
                           bot_token=token_val, group_id=group_val, 
                           bot_time_str=bot_time_str, bot_time_parts=json.dumps(bot_time_parts))

@app.route('/api/data')
@login_required
def api_data():
    conn = get_db_connection()
    tickets = [dict(r) for r in conn.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT 1000").fetchall()]
    it_staff = [dict(r) for r in conn.execute("SELECT * FROM it_staff").fetchall()]
    conn.close()
    return jsonify({'tickets': tickets, 'it_staff': it_staff})

@app.route('/api/export_db')
@login_required
def api_export_db():
    if session.get('role') != 'superadmin':
        return "Truy cập bị từ chối! Chỉ SuperAdmin mới được xuất Database.", 403
    
    db_path = 'helpdesk.db'
    if os.path.exists(db_path):
        filename = f"helpdesk_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
        return send_file(db_path, as_attachment=True, download_name=filename)
    return "Không tìm thấy file Database trên server!", 404

@app.route('/api/save_settings', methods=['POST'])
@login_required
def api_save_settings():
    if session.get('role') == 'manager': return jsonify({"success": False, "error": "Quản lý không có quyền sửa cấu hình!"})
    data = request.json
    token = data.get('bot_token')
    group_id = data.get('group_id')
    custom_time = data.get('custom_time')

    if not token or not group_id: 
        return jsonify({"success": False, "error": "Không được để trống!"})
        
    token_str = token.strip()
    group_str = group_id.strip()

    test_url = f"https://api.telegram.org/bot{token_str}/sendMessage"
    test_payload = {
        "chat_id": group_str,
        "text": "🟢 **Hệ thống IT Helpdesk đã kết nối thành công với nhóm này!**\nSẵn sàng nhận và điều phối Ticket.",
        "parse_mode": "Markdown"
    }
    
    try:
        r = requests.post(test_url, json=test_payload, timeout=5)
        resp_data = r.json()
        
        if not resp_data.get('ok'):
            error_msg = resp_data.get('description', 'Lỗi không xác định')
            if "chat not found" in error_msg.lower():
                return jsonify({"success": False, "error": "Sai ID Nhóm! Vui lòng kiểm tra lại."})
            elif "bot is not a member" in error_msg.lower():
                return jsonify({"success": False, "error": "Bot chưa được thêm vào nhóm này! Hãy thêm Bot vào nhóm trước."})
            else:
                return jsonify({"success": False, "error": f"Lỗi Telegram: {error_msg}"})
                
    except Exception as e:
        return jsonify({"success": False, "error": "Không thể kết nối tới máy chủ Telegram. Hãy kiểm tra mạng!"})

    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('BOT_TOKEN', ?)", (token_str,))
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('GROUP_IT_ID', ?)", (group_str,))
    
    if custom_time:
        try:
            target_time = datetime.strptime(custom_time, '%Y-%m-%dT%H:%M')
            server_now = datetime.now()
            offset_sec = int((target_time - server_now).total_seconds())
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('TIME_OFFSET', ?)", (str(offset_sec),))
        except Exception:
            pass
    
    conn.commit()
    conn.close()
    
    return jsonify({"success": True})

@app.route('/api/add_admin', methods=['POST'])
@login_required
def api_add_admin():
    if session.get('role') == 'manager': return jsonify({"success": False, "error": "Bạn không có quyền thêm tài khoản!"})
    data = request.json
    u, p, r = data.get('username'), data.get('password'), data.get('role', 'admin')
    if not u or not p: return jsonify({"success": False, "error": "Thiếu thông tin!"})
    conn = get_db_connection()
    if conn.execute("SELECT * FROM web_admins WHERE username=?", (u,)).fetchone():
        conn.close(); return jsonify({"success": False, "error": "Tài khoản tồn tại!"})
    hashed_pwd = generate_password_hash(p)
    conn.execute("INSERT INTO web_admins (username, password, role) VALUES (?, ?, ?)", (u, hashed_pwd, r)); conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/admin_reset_password', methods=['POST'])
@login_required
def api_admin_reset_password():
    if session.get('role') == 'manager': return jsonify({"success": False, "error": "Bạn không có quyền sửa mật khẩu!"})
    data = request.json
    if not data.get('username') or not data.get('new_password'): return jsonify({"success": False, "error": "Dữ liệu sai"})
    hashed_pwd = generate_password_hash(data.get('new_password'))
    conn = get_db_connection(); conn.execute("UPDATE web_admins SET password=? WHERE username=?", (hashed_pwd, data.get('username'))); conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/delete_admin/<int:admin_id>', methods=['POST'])
@login_required
def api_delete_admin(admin_id):
    if session.get('role') == 'manager': return jsonify({"success": False, "error": "Bạn không có quyền xóa tài khoản!"})
    conn = get_db_connection()
    if conn.execute("SELECT username FROM web_admins WHERE id=?", (admin_id,)).fetchone()['username'] == 'admin':
        conn.close(); return jsonify({"success": False, "error": "Không xóa Admin gốc!"})
    conn.execute("DELETE FROM web_admins WHERE id=?", (admin_id,)); conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/add_department', methods=['POST'])
@login_required
def api_add_department():
    if session.get('role') == 'manager': return jsonify({"success": False, "error": "Bạn không có quyền thao tác!"}), 403
    name = request.json.get('dept_name')
    if not name: return jsonify({"success": False, "error": "Thiếu tên"}), 400
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO departments (name) VALUES (?)", (name,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e: 
        return jsonify({"success": False, "error": str(e)})
    finally: 
        conn.close()

@app.route('/api/delete_department/<int:dept_id>', methods=['POST'])
@login_required
def api_delete_department(dept_id):
    if session.get('role') == 'manager': return jsonify({"success": False, "error": "Bạn không có quyền thao tác!"}), 403
    conn = get_db_connection()
    conn.execute("DELETE FROM departments WHERE id=?", (dept_id,))
    conn.commit()
    conn.close()
@app.route('/api/create_ticket', methods=['POST'])
@login_required
def api_create_ticket():
    if session.get('role') == 'manager': return jsonify({"success": False, "error": "Quản lý chỉ có quyền xem!"})
    data = request.json or {}
    user_name = (data.get('user_name') or '').strip()
    dept = (data.get('dept') or '').strip()
    issue = (data.get('issue') or '').strip()
    it_id = data.get('it_id')
    status = data.get('status') or 'Hoàn thành'
    rating = data.get('rating')
    
    if not user_name or not dept or not issue:
        return jsonify({"success": False, "error": "Vui lòng điền đầy đủ Tên khách, Phòng ban và Nội dung sự cố!"})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    it_name = None
    if it_id:
        try:
            it_id = int(it_id)
            it_row = cursor.execute("SELECT it_real_name FROM it_staff WHERE it_id=?", (it_id,)).fetchone()
            if it_row:
                it_name = it_row['it_real_name']
        except Exception:
            it_id = None
            
    time_offset_row = cursor.execute("SELECT value FROM settings WHERE key='TIME_OFFSET'").fetchone()
    offset_sec = int(time_offset_row['value']) if time_offset_row else 0
    now_time = datetime.now() + timedelta(seconds=offset_sec)
    now_str = now_time.strftime("%Y-%m-%d %H:%M:%S")
    
    custom_created = data.get('created_at')
    if custom_created:
        try:
            created_at = custom_created.replace('T', ' ')
            if len(created_at) == 16: created_at += ":00"
        except Exception:
            created_at = now_str
    else:
        created_at = now_str

    custom_completed = data.get('completed_at')
    if status == 'Hoàn thành':
        if custom_completed:
            try:
                completed_at = custom_completed.replace('T', ' ')
                if len(completed_at) == 16: completed_at += ":00"
            except Exception:
                completed_at = created_at
        else:
            completed_at = created_at
    else:
        completed_at = None
    
    rating_val = int(rating) if rating else (5 if status == 'Hoàn thành' else None)
    
    cursor.execute("""
        INSERT INTO tickets (user_id, user_name, dept, issue, status, it_id, it_name, created_at, completed_at, rating)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (0, user_name, dept, issue, status, it_id, it_name, created_at, completed_at, rating_val))
    
    ticket_id = cursor.lastrowid
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('LAST_TICKET_UPDATE', ?)", (str(datetime.now().timestamp()),))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "ticket_id": ticket_id})

@app.route('/api/update_ticket', methods=['POST'])
@login_required
def api_update_ticket():
    if session.get('role') == 'manager': return jsonify({"success": False, "error": "Quản lý chỉ có quyền xem!"})
    data = request.json or {}
    t_id = data.get('id')
    issue = data.get('issue')
    it_id = data.get('it_id')
    it_name = data.get('it_name')
    sup_names = data.get('support_it_names')
    status = data.get('status')
    
    custom_created = data.get('created_at')
    custom_completed = data.get('completed_at')
    
    conn = get_db_connection()
    current_t = conn.execute("SELECT completed_at, created_at FROM tickets WHERE id=?", (t_id,)).fetchone()
    completed_at_val = current_t['completed_at'] if current_t and current_t['completed_at'] else None
    
    if custom_completed and status == 'Hoàn thành':
        try:
            completed_at_val = custom_completed.replace('T', ' ')
            if len(completed_at_val) == 16: completed_at_val += ":00"
        except Exception: pass
    elif status == 'Hoàn thành' and not completed_at_val:
        time_offset_row = conn.execute("SELECT value FROM settings WHERE key='TIME_OFFSET'").fetchone()
        offset_sec = int(time_offset_row['value']) if time_offset_row else 0
        completed_at_val = (datetime.now() + timedelta(seconds=offset_sec)).strftime("%Y-%m-%d %H:%M:%S")
    elif status != 'Hoàn thành':
        completed_at_val = None

    if custom_created:
        try:
            created_at_val = custom_created.replace('T', ' ')
            if len(created_at_val) == 16: created_at_val += ":00"
            conn.execute("UPDATE tickets SET created_at=? WHERE id=?", (created_at_val, t_id))
        except Exception: pass

    conn.execute("UPDATE tickets SET issue=?, it_id=?, it_name=?, support_it_names=?, status=?, completed_at=? WHERE id=?", 
                 (issue, it_id, it_name, sup_names, status, completed_at_val, t_id))
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('LAST_TICKET_UPDATE', ?)", (str(datetime.now().timestamp()),))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/delete_ticket/<int:t_id>', methods=['POST'])
@login_required
def api_delete_ticket(t_id):
    if session.get('role') == 'manager': return jsonify({"success": False, "error": "Quản lý chỉ có quyền xem!"})
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM active_sessions WHERE ticket_id=?", (t_id,))
        conn.execute("DELETE FROM tickets WHERE id=?", (t_id,))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('LAST_TICKET_UPDATE', ?)", (str(datetime.now().timestamp()),))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"success": True})

@app.route('/api/update_it', methods=['POST'])
@login_required
def api_update_it():
    if session.get('role') == 'manager': return jsonify({"success": False, "error": "Quản lý chỉ có quyền xem!"})
    data = request.json
    conn = get_db_connection()
    conn.execute("UPDATE it_staff SET it_real_name=?, it_phone=? WHERE it_id=?", 
                 (data.get('name'), data.get('phone'), data.get('id')))
    conn.execute("UPDATE tickets SET it_name=? WHERE it_id=?", (data.get('name'), data.get('id')))
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('LAST_TICKET_UPDATE', ?)", (str(datetime.now().timestamp()),))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/delete_it/<int:it_id>', methods=['POST'])
@login_required
def api_delete_it(it_id):
    if session.get('role') == 'manager': return jsonify({"success": False, "error": "Quản lý chỉ có quyền xem!"})
    conn = get_db_connection()
    conn.execute("DELETE FROM it_staff WHERE it_id=?", (it_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/update_user', methods=['POST'])
@login_required
def api_update_user():
    if session.get('role') == 'manager': return jsonify({"success": False, "error": "Quản lý chỉ có quyền xem!"})
    data = request.json
    conn = get_db_connection()
    conn.execute("UPDATE users SET name=?, dept=? WHERE user_id=?", 
                 (data.get('name'), data.get('dept'), data.get('id')))
    conn.execute("UPDATE tickets SET user_name=?, dept=? WHERE user_id=?", (data.get('name'), data.get('dept'), data.get('id')))
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('LAST_TICKET_UPDATE', ?)", (str(datetime.now().timestamp()),))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/delete_user/<int:u_id>', methods=['POST'])
@login_required
def api_delete_user(u_id):
    if session.get('role') == 'manager': return jsonify({"success": False, "error": "Quản lý chỉ có quyền xem!"})
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE user_id=?", (u_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)