"""
Flask Web Application Factory
Initializes the Flask application, database migrations for web admins, and registers blueprints/routes.
"""
import os
from flask import Flask
from werkzeug.security import generate_password_hash
from database.connection import get_db_connection

def init_web_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    except Exception:
        pass
    cursor.execute('CREATE TABLE IF NOT EXISTS web_admins (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS departments (id INTEGER PRIMARY KEY, name TEXT UNIQUE, topic_id INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')

    offset_exist = cursor.execute("SELECT * FROM settings WHERE key='TIME_OFFSET'").fetchone()
    if not offset_exist:
        cursor.execute("INSERT INTO settings (key, value) VALUES ('TIME_OFFSET', '0')")

    columns_to_add = [
        ('tickets', 'rating INTEGER'),
        ('it_staff', 'it_phone TEXT'),
        ('tickets', 'support_it_ids TEXT'),
        ('tickets', 'support_it_names TEXT'),
        ('tickets', 'completed_at TEXT')
    ]
    for table, col_def in columns_to_add:
        try:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {col_def}')
        except Exception:
            pass

    admin_exist = cursor.execute("SELECT * FROM web_admins WHERE username='admin'").fetchone()
    if not admin_exist:
        cursor.execute("INSERT INTO web_admins (username, password, role) VALUES ('admin', ?, 'superadmin')", (generate_password_hash('123456'),))
    
    # Auto migrate any existing plain text admin passwords to hashed passwords
    admins = cursor.execute("SELECT id, password FROM web_admins").fetchall()
    for row in admins:
        pwd = row['password']
        if pwd and not (pwd.startswith('scrypt:') or pwd.startswith('pbkdf2:')):
            hashed_pwd = generate_password_hash(pwd)
            cursor.execute("UPDATE web_admins SET password = ? WHERE id = ?", (hashed_pwd, row['id']))
    
    token_exist = cursor.execute("SELECT * FROM settings WHERE key='BOT_TOKEN'").fetchone()
    if not token_exist:
        cursor.execute("INSERT INTO settings (key, value) VALUES ('BOT_TOKEN', 'ĐIỀN TOKEN VÀO ĐÂY')")
    
    group_exist = cursor.execute("SELECT * FROM settings WHERE key='GROUP_IT_ID'").fetchone()
    if not group_exist:
        cursor.execute("INSERT INTO settings (key, value) VALUES ('GROUP_IT_ID', 'ĐIỀN ID NHÓM VÀO ĐÂY')")

    conn.commit()
    conn.close()

def create_app():
    app = Flask(__name__, template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'))
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'Sieu_Bao_Mat_Helpdesk_2026')
    
    init_web_db()
    
    from web.blueprints import register_blueprints
    register_blueprints(app)
    
    return app
