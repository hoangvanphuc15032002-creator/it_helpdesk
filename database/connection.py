"""
Database Connection Management
Handles SQLite connections with WAL journal mode and busy timeout settings.
"""
import os
import sqlite3

def get_default_db_path():
    return os.environ.get('DB_PATH', 'helpdesk.db')

def connect_db(db_path=None):
    if not db_path:
        db_path = get_default_db_path()
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
    except Exception:
        pass
    return conn

def get_db_connection(db_path=None):
    conn = connect_db(db_path)
    conn.row_factory = sqlite3.Row
    return conn

