"""
Main Dashboard Views Blueprint
Renders the admin dashboard template with database context.
"""
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template
from database.connection import get_db_connection
from web.middleware import login_required

views_bp = Blueprint('views', __name__)

@views_bp.route('/')
@views_bp.route('/admin', endpoint='admin_dashboard')
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
