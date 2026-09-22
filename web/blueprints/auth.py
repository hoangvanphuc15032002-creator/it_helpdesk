"""
Authentication Blueprint
Handles login and logout for web admins.
"""
from flask import Blueprint, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from database.connection import get_db_connection

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '')
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
            return redirect(url_for('views.admin_dashboard'))
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

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
