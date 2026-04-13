from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from functools import wraps
import sqlite3
import json
import requests
from pyngrok import ngrok 

app = Flask(__name__)
app.secret_key = 'Sieu_Bao_Mat_Helpdesk_2026'

# ==========================================
# THÔNG TIN CẤU HÌNH KIẾN TRÚC 2 NHÓM
# ==========================================
BOT_TOKEN = '8786795332:AAEK78FOden7Yo9slp16IAnZJaD4qZ65_yA'
GROUP_IT_ID = -5228934914 
GROUP_COMPANY_ID = -1003858230465

def get_db_connection():
    conn = sqlite3.connect('helpdesk.db', timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# KHỞI TẠO DATABASE MỚI CHO TRANG WEB
def init_web_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Bảng Quản trị viên Web
    cursor.execute('CREATE TABLE IF NOT EXISTS web_admins (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)')
    # Bảng Quản lý Phòng ban
    cursor.execute('CREATE TABLE IF NOT EXISTS departments (id INTEGER PRIMARY KEY, name TEXT UNIQUE, topic_id INTEGER)')
    
    # --- CẬP NHẬT CẤU TRÚC CHO RATING VÀ PHONE ---
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN rating INTEGER')
    except: pass
    try: cursor.execute('ALTER TABLE it_staff ADD COLUMN it_phone TEXT')
    except: pass

    # Tạo tài khoản Admin mặc định nếu chưa có
    admin_exist = cursor.execute("SELECT * FROM web_admins WHERE username='admin'").fetchone()
    if not admin_exist:
        cursor.execute("INSERT INTO web_admins (username, password, role) VALUES ('admin', '123456', 'superadmin')")
    
    conn.commit()
    conn.close()

init_web_db()

# ==========================================
# MIDDLEWARE: KIỂM TRA ĐĂNG NHẬP
# ==========================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# ROUTE: ĐĂNG NHẬP & ĐĂNG XUẤT
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form['username'], request.form['password']
        conn = get_db_connection()
        admin = conn.execute("SELECT * FROM web_admins WHERE username=? AND password=?", (u, p)).fetchone()
        conn.close()
        if admin:
            session.update({'logged_in': True, 'username': admin['username'], 'role': admin['role']})
            return redirect(url_for('admin_dashboard'))
        return "<div style='text-align: center; margin-top: 50px; font-family: sans-serif;'>❌ Sai tài khoản hoặc mật khẩu! <br><br><a href='/login' style='padding: 10px 20px; background: #ef4444; color: white; text-decoration: none; border-radius: 8px;'>Thử lại</a></div>"
            
    return '''
        <div style="max-width: 400px; margin: 100px auto; text-align: center; font-family: sans-serif; background: #fff; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h2 style="color: #1e293b; margin-bottom: 24px;">ĐĂNG NHẬP HỆ THỐNG IT</h2>
            <form method="post">
                <p><input type="text" name="username" placeholder="Tài khoản" required style="padding: 12px; width: 100%; box-sizing: border-box; border: 1px solid #d1d5db; border-radius: 8px; margin-bottom: 16px;"></p>
                <p><input type="password" name="password" placeholder="Mật khẩu" required style="padding: 12px; width: 100%; box-sizing: border-box; border: 1px solid #d1d5db; border-radius: 8px; margin-bottom: 24px;"></p>
                <button type="submit" style="padding: 12px 24px; background: #4f46e5; color: white; border: none; border-radius: 8px; cursor: pointer; width: 100%; font-weight: bold;">Đăng nhập</button>
            </form>
        </div>
    '''

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# ROUTE: DASHBOARD CHÍNH & ADMIN
# ==========================================
@app.route('/')
@app.route('/admin')
@login_required
def admin_dashboard():
    conn = get_db_connection()
    tickets = [dict(r) for r in conn.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT 1000").fetchall()]
    depts = conn.execute("SELECT * FROM departments ORDER BY id DESC").fetchall()
    users = conn.execute("SELECT * FROM users ORDER BY user_id DESC").fetchall()
    it_staff = conn.execute("SELECT * FROM it_staff").fetchall()
    admins = conn.execute("SELECT id, username, role FROM web_admins ORDER BY id ASC").fetchall()
    conn.close()
    
    return render_template('admin.html', 
                           tickets_json=json.dumps(tickets), 
                           departments_json=json.dumps([r['name'] for r in depts]), 
                           depts=depts, users=users, it_staff=it_staff, admins=admins)

@app.route('/api/data')
@login_required
def api_data():
    conn = get_db_connection()
    tickets = [dict(r) for r in conn.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT 1000").fetchall()]
    conn.close()
    return jsonify({'tickets': tickets})

# ==========================================
# API QUẢN LÝ TÀI KHOẢN ADMIN
# ==========================================
@app.route('/api/add_admin', methods=['POST'])
@login_required
def api_add_admin():
    data = request.json
    u = data.get('username')
    p = data.get('password')
    if not u or not p: 
        return jsonify({"success": False, "error": "Thiếu thông tin!"})
    
    conn = get_db_connection()
    exist = conn.execute("SELECT * FROM web_admins WHERE username=?", (u,)).fetchone()
    if exist:
        conn.close()
        return jsonify({"success": False, "error": "Tài khoản này đã tồn tại!"})
    
    conn.execute("INSERT INTO web_admins (username, password, role) VALUES (?, ?, 'admin')", (u, p))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/admin_reset_password', methods=['POST'])
@login_required
def api_admin_reset_password():
    data = request.json
    target_u = data.get('username')
    new_p = data.get('new_password')
    
    if not target_u or not new_p:
        return jsonify({"success": False, "error": "Dữ liệu không hợp lệ"})
        
    conn = get_db_connection()
    conn.execute("UPDATE web_admins SET password=? WHERE username=?", (new_p, target_u))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/delete_admin/<int:admin_id>', methods=['POST'])
@login_required
def api_delete_admin(admin_id):
    conn = get_db_connection()
    target = conn.execute("SELECT username FROM web_admins WHERE id=?", (admin_id,)).fetchone()
    if target and target['username'] == 'admin':
        conn.close()
        return jsonify({"success": False, "error": "Không thể xóa tài khoản Super Admin gốc!"})
    
    conn.execute("DELETE FROM web_admins WHERE id=?", (admin_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# ==========================================
# API QUẢN LÝ PHÒNG BAN
# ==========================================
@app.route('/api/add_department', methods=['POST'])
@login_required
def api_add_department():
    name = request.json.get('dept_name')
    if not name: return jsonify({"success": False, "error": "Thiếu tên"}), 400
    conn = get_db_connection()
    try:
        bot_info = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe").json()
        bot_username = bot_info['result']['username']
        
        topic_res = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/createForumTopic", json={"chat_id": GROUP_COMPANY_ID, "name": name}).json()
        if not topic_res.get('ok'): return jsonify({"success": False, "error": topic_res.get('description')}), 400
        tid = topic_res['result']['message_thread_id']
        
        kb = {"inline_keyboard": [[{"text": f"🆘 Báo sự cố {name}", "url": f"https://t.me/{bot_username}?start={name.encode('utf-8').hex()}"}]]}
        msg = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": GROUP_COMPANY_ID, "message_thread_id": tid, "text": f"🏢 **CỔNG HỖ TRỢ IT - {name.upper()}**", "parse_mode": "Markdown", "reply_markup": kb}).json()
        if msg.get('ok'): requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/pinChatMessage", json={"chat_id": GROUP_COMPANY_ID, "message_id": msg['result']['message_id']})
        
        conn.execute("INSERT INTO departments (name, topic_id) VALUES (?, ?)", (name, tid))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e: return jsonify({"success": False, "error": str(e)})
    finally: conn.close()

@app.route('/api/delete_department/<int:dept_id>', methods=['POST'])
@login_required
def api_delete_department(dept_id):
    conn = get_db_connection()
    dept = conn.execute("SELECT * FROM departments WHERE id=?", (dept_id,)).fetchone()
    if dept:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteForumTopic", json={"chat_id": GROUP_COMPANY_ID, "message_thread_id": dept['topic_id']})
        conn.execute("DELETE FROM departments WHERE id=?", (dept_id,))
        conn.commit()
    conn.close()
    return jsonify({"success": True})

# ==========================================
# KHỞI CHẠY SERVER
# ==========================================
if __name__ == '__main__':
    try:
        public_url = ngrok.connect(8080).public_url
        print(f"\n🚀 LINK ONLINE: {public_url}\n")
    except: pass
    app.run(host='0.0.0.0', port=8080)