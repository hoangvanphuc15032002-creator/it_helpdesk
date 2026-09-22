"""
System Settings & Admin API Blueprint
Handles Admin account management, Department CRUD, Settings saving, and Database Export.
"""
import os
import requests
from datetime import datetime
from flask import Blueprint, jsonify, request, session, send_file
from werkzeug.security import generate_password_hash
from database.connection import get_db_connection
from web.middleware import login_required

system_bp = Blueprint('system', __name__)

@system_bp.route('/api/export_db')
@login_required
def api_export_db():
    if session.get('role') != 'superadmin':
        return "Truy cập bị từ chối! Chỉ SuperAdmin mới được xuất Database.", 403
    
    db_path = 'helpdesk.db'
    if os.path.exists(db_path):
        filename = f"helpdesk_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
        return send_file(db_path, as_attachment=True, download_name=filename)
    return "Không tìm thấy file Database trên server!", 404

@system_bp.route('/api/save_settings', methods=['POST'])
@login_required
def api_save_settings():
    if session.get('role') == 'manager':
        return jsonify({"success": False, "error": "Quản lý không có quyền sửa cấu hình!"})
    data = request.json or {}
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
                
    except Exception:
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

@system_bp.route('/api/add_admin', methods=['POST'])
@login_required
def api_add_admin():
    if session.get('role') == 'manager':
        return jsonify({"success": False, "error": "Bạn không có quyền thêm tài khoản!"})
    data = request.json or {}
    u, p, r = data.get('username'), data.get('password'), data.get('role', 'admin')
    if not u or not p:
        return jsonify({"success": False, "error": "Thiếu thông tin!"})
    conn = get_db_connection()
    if conn.execute("SELECT * FROM web_admins WHERE username=?", (u,)).fetchone():
        conn.close()
        return jsonify({"success": False, "error": "Tài khoản tồn tại!"})
    hashed_pwd = generate_password_hash(p)
    conn.execute("INSERT INTO web_admins (username, password, role) VALUES (?, ?, ?)", (u, hashed_pwd, r))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@system_bp.route('/api/admin_reset_password', methods=['POST'])
@login_required
def api_admin_reset_password():
    if session.get('role') == 'manager':
        return jsonify({"success": False, "error": "Bạn không có quyền sửa mật khẩu!"})
    data = request.json or {}
    if not data.get('username') or not data.get('new_password'):
        return jsonify({"success": False, "error": "Dữ liệu sai"})
    hashed_pwd = generate_password_hash(data.get('new_password'))
    conn = get_db_connection()
    conn.execute("UPDATE web_admins SET password=? WHERE username=?", (hashed_pwd, data.get('username')))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@system_bp.route('/api/delete_admin/<int:admin_id>', methods=['POST'])
@login_required
def api_delete_admin(admin_id):
    if session.get('role') == 'manager':
        return jsonify({"success": False, "error": "Bạn không có quyền xóa tài khoản!"})
    conn = get_db_connection()
    if conn.execute("SELECT username FROM web_admins WHERE id=?", (admin_id,)).fetchone()['username'] == 'admin':
        conn.close()
        return jsonify({"success": False, "error": "Không xóa Admin gốc!"})
    conn.execute("DELETE FROM web_admins WHERE id=?", (admin_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@system_bp.route('/api/add_department', methods=['POST'])
@login_required
def api_add_department():
    if session.get('role') == 'manager':
        return jsonify({"success": False, "error": "Bạn không có quyền thao tác!"}), 403
    name = (request.json or {}).get('dept_name')
    if not name:
        return jsonify({"success": False, "error": "Thiếu tên"}), 400
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO departments (name) VALUES (?)", (name,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e: 
        return jsonify({"success": False, "error": str(e)})
    finally: 
        conn.close()

@system_bp.route('/api/delete_department/<int:dept_id>', methods=['POST'])
@login_required
def api_delete_department(dept_id):
    if session.get('role') == 'manager':
        return jsonify({"success": False, "error": "Bạn không có quyền thao tác!"}), 403
    conn = get_db_connection()
    conn.execute("DELETE FROM departments WHERE id=?", (dept_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})
