"""
Database Connection Management
Handles SQLite connections with WAL journal mode and busy timeout settings.
"""
import glob
import os
import sqlite3

def get_default_db_path():
    if os.environ.get('DB_PATH'):
        return os.environ['DB_PATH']
    if os.path.exists('helpdesk.db'):
        return 'helpdesk.db'
    
    # Auto-detect existing backup db files in the directory (sorted by newest first)
    backup_dbs = sorted(glob.glob('helpdesk_*.db'), key=os.path.getmtime, reverse=True)
    if backup_dbs:
        return backup_dbs[0]
        
    return 'helpdesk.db'

def connect_db(db_path=None):
    if db_path is None or db_path == 'helpdesk.db':
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

