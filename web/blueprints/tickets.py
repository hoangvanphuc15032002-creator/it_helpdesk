"""
Tickets API Blueprint
Manages real-time ticket fetching, creation, modification, and deletion endpoints.
"""
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, session
from database.connection import get_db_connection
from web.middleware import login_required

tickets_bp = Blueprint('tickets', __name__)

@tickets_bp.route('/api/data')
@login_required
def api_data():
    conn = get_db_connection()
    tickets = [dict(r) for r in conn.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT 1000").fetchall()]
    it_staff = [dict(r) for r in conn.execute("SELECT * FROM it_staff").fetchall()]
    conn.close()
    return jsonify({'tickets': tickets, 'it_staff': it_staff})

@tickets_bp.route('/api/create_ticket', methods=['POST'])
@login_required
def api_create_ticket():
    if session.get('role') == 'manager':
        return jsonify({"success": False, "error": "Quản lý chỉ có quyền xem!"})
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

@tickets_bp.route('/api/update_ticket', methods=['POST'])
@login_required
def api_update_ticket():
    if session.get('role') == 'manager':
        return jsonify({"success": False, "error": "Quản lý chỉ có quyền xem!"})
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
        except Exception:
            pass
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
        except Exception:
            pass

    conn.execute("UPDATE tickets SET issue=?, it_id=?, it_name=?, support_it_names=?, status=?, completed_at=? WHERE id=?", 
                 (issue, it_id, it_name, sup_names, status, completed_at_val, t_id))
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('LAST_TICKET_UPDATE', ?)", (str(datetime.now().timestamp()),))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@tickets_bp.route('/api/delete_ticket/<int:t_id>', methods=['POST'])
@login_required
def api_delete_ticket(t_id):
    if session.get('role') == 'manager':
        return jsonify({"success": False, "error": "Quản lý chỉ có quyền xem!"})
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM active_sessions WHERE ticket_id=?", (t_id,))
        conn.execute("DELETE FROM tickets WHERE id=?", (t_id,))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('LAST_TICKET_UPDATE', ?)", (str(datetime.now().timestamp()),))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"success": True})
