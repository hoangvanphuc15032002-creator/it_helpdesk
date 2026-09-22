"""
IT Staff & Customers API Blueprint
Handles IT Staff and Customer management endpoints.
"""
from flask import Blueprint, jsonify, request, session
from database.connection import get_db_connection
from web.middleware import login_required

staff_users_bp = Blueprint('staff_users', __name__)

@staff_users_bp.route('/api/update_it', methods=['POST'])
@login_required
def api_update_it():
    if session.get('role') == 'manager':
        return jsonify({"success": False, "error": "Quản lý chỉ có quyền xem!"})
    data = request.json or {}
    conn = get_db_connection()
    conn.execute("UPDATE it_staff SET it_real_name=?, it_phone=? WHERE it_id=?", 
                 (data.get('name'), data.get('phone'), data.get('id')))
    conn.execute("UPDATE tickets SET it_name=? WHERE it_id=?", (data.get('name'), data.get('id')))
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('LAST_TICKET_UPDATE', ?)", (str(datetime_now_timestamp()),))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

def datetime_now_timestamp():
    from datetime import datetime
    return str(datetime.now().timestamp())

@staff_users_bp.route('/api/delete_it/<int:it_id>', methods=['POST'])
@login_required
def api_delete_it(it_id):
    if session.get('role') == 'manager':
        return jsonify({"success": False, "error": "Quản lý chỉ có quyền xem!"})
    conn = get_db_connection()
    conn.execute("DELETE FROM it_staff WHERE it_id=?", (it_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@staff_users_bp.route('/api/update_user', methods=['POST'])
@login_required
def api_update_user():
    if session.get('role') == 'manager':
        return jsonify({"success": False, "error": "Quản lý chỉ có quyền xem!"})
    data = request.json or {}
    conn = get_db_connection()
    conn.execute("UPDATE users SET name=?, dept=? WHERE user_id=?", 
                 (data.get('name'), data.get('dept'), data.get('id')))
    conn.execute("UPDATE tickets SET user_name=?, dept=? WHERE user_id=?", (data.get('name'), data.get('dept'), data.get('id')))
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('LAST_TICKET_UPDATE', ?)", (str(datetime_now_timestamp()),))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@staff_users_bp.route('/api/delete_user/<int:u_id>', methods=['POST'])
@login_required
def api_delete_user(u_id):
    if session.get('role') == 'manager':
        return jsonify({"success": False, "error": "Quản lý chỉ có quyền xem!"})
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE user_id=?", (u_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})
