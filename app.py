from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from functools import wraps
import sqlite3
import json
import requests

app = Flask(__name__)
app.secret_key = 'Sieu_Bao_Mat_Helpdesk_2026'

def get_db_connection():
    conn = sqlite3.connect('helpdesk.db', timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_web_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS web_admins (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)')
    
    cursor.execute('CREATE TABLE IF NOT EXISTS departments (id INTEGER PRIMARY KEY, name TEXT UNIQUE, topic_id INTEGER)')
    
    cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')

    try: cursor.execute('ALTER TABLE tickets ADD COLUMN rating INTEGER')
    except: pass
    try: cursor.execute('ALTER TABLE it_staff ADD COLUMN it_phone TEXT')
    except: pass
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN support_it_ids TEXT')
    except: pass 
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN support_it_names TEXT')
    except: pass 

    admin_exist = cursor.execute("SELECT * FROM web_admins WHERE username='admin'").fetchone()
    if not admin_exist: cursor.execute("INSERT INTO web_admins (username, password, role) VALUES ('admin', '123456', 'superadmin')")
    
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
    
    bot_token = conn.execute("SELECT value FROM settings WHERE key='BOT_TOKEN'").fetchone()
    group_id = conn.execute("SELECT value FROM settings WHERE key='GROUP_IT_ID'").fetchone()
    
    token_val = bot_token['value'] if bot_token else ""
    group_val = group_id['value'] if group_id else ""

    conn.close()
    
    return render_template('admin.html', 
                           tickets_json=json.dumps(tickets), 
                           departments_json=json.dumps([r['name'] for r in depts]), 
                           depts=depts, users=users, it_staff=it_staff, admins=admins,
                           bot_token=token_val, group_id=group_val)

@app.route('/api/data')
@login_required
def api_data():
    conn = get_db_connection()
    tickets = [dict(r) for r in conn.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT 1000").fetchall()]
    conn.close()
    return jsonify({'tickets': tickets})

@app.route('/api/save_settings', methods=['POST'])
@login_required
def api_save_settings():
    if session.get('role') != 'superadmin':
        return jsonify({"success": False, "error": "Chỉ SuperAdmin mới được đổi cấu hình!"})
        
    data = request.json
    token = data.get('bot_token')
    group_id = data.get('group_id')
    
    if not token or not group_id: 
        return jsonify({"success": False, "error": "Không được để trống!"})
        
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('BOT_TOKEN', ?)", (token.strip(),))
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('GROUP_IT_ID', ?)", (group_id.strip(),))
    conn.commit()
    conn.close()
    
    return jsonify({"success": True})

@app.route('/api/add_admin', methods=['POST'])
@login_required
def api_add_admin():
    data = request.json
    u, p = data.get('username'), data.get('password')
    if not u or not p: return jsonify({"success": False, "error": "Thiếu thông tin!"})
    conn = get_db_connection()
    if conn.execute("SELECT * FROM web_admins WHERE username=?", (u,)).fetchone():
        conn.close(); return jsonify({"success": False, "error": "Tài khoản tồn tại!"})
    conn.execute("INSERT INTO web_admins (username, password, role) VALUES (?, ?, 'admin')", (u, p)); conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/admin_reset_password', methods=['POST'])
@login_required
def api_admin_reset_password():
    data = request.json
    if not data.get('username') or not data.get('new_password'): return jsonify({"success": False, "error": "Dữ liệu sai"})
    conn = get_db_connection(); conn.execute("UPDATE web_admins SET password=? WHERE username=?", (data.get('new_password'), data.get('username'))); conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/delete_admin/<int:admin_id>', methods=['POST'])
@login_required
def api_delete_admin(admin_id):
    conn = get_db_connection()
    if conn.execute("SELECT username FROM web_admins WHERE id=?", (admin_id,)).fetchone()['username'] == 'admin':
        conn.close(); return jsonify({"success": False, "error": "Không xóa Admin gốc!"})
    conn.execute("DELETE FROM web_admins WHERE id=?", (admin_id,)); conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/add_department', methods=['POST'])
@login_required
def api_add_department():
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
    conn = get_db_connection()
    conn.execute("DELETE FROM departments WHERE id=?", (dept_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)