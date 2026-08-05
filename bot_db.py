import sqlite3

def connect_db():
    conn = sqlite3.connect('helpdesk.db', timeout=30, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
    except:
        pass
    return conn

def init_db():
    conn = connect_db()
    cursor = conn.cursor()
    try: cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    except: pass

    cursor.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, user_name TEXT, dept TEXT, issue TEXT, status TEXT, it_id INTEGER, it_name TEXT, created_at TEXT, rating INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, dept TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS it_staff (it_id INTEGER PRIMARY KEY, it_real_name TEXT, it_phone TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS departments (id INTEGER PRIMARY KEY, name TEXT UNIQUE, topic_id INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    
    cursor.execute('CREATE TABLE IF NOT EXISTS active_sessions (user_id INTEGER, ticket_id INTEGER, role TEXT, topic_id INTEGER, PRIMARY KEY (user_id, ticket_id))')
    cursor.execute('CREATE TABLE IF NOT EXISTS user_states_db (user_id INTEGER PRIMARY KEY, step TEXT, temp_data TEXT)')
    
    try:
        info = cursor.execute("PRAGMA table_info(active_sessions)").fetchall()
        pk_cols = [row[1] for row in info if row[5] > 0]
        if pk_cols == ['user_id']:
            cursor.execute("CREATE TABLE active_sessions_new (user_id INTEGER, ticket_id INTEGER, role TEXT, topic_id INTEGER, PRIMARY KEY (user_id, ticket_id))")
            cursor.execute("INSERT OR IGNORE INTO active_sessions_new (user_id, ticket_id, role, topic_id) SELECT user_id, ticket_id, role, topic_id FROM active_sessions")
            cursor.execute("DROP TABLE active_sessions")
            cursor.execute("ALTER TABLE active_sessions_new RENAME TO active_sessions")
    except Exception as e:
        print("Migration active_sessions exception:", e)

    try: cursor.execute('ALTER TABLE tickets ADD COLUMN rating INTEGER')
    except: pass
    try: cursor.execute('ALTER TABLE it_staff ADD COLUMN it_phone TEXT')
    except: pass
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN it_name TEXT')
    except: pass 
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN support_it_ids TEXT')
    except: pass 
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN support_it_names TEXT')
    except: pass 
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN group_support_msg_id INTEGER')
    except: pass 
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN group_msg_id INTEGER') 
    except: pass
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN it_msg_id INTEGER')
    except: pass
    try: cursor.execute('ALTER TABLE it_staff ADD COLUMN workspace_group_id INTEGER')
    except: pass
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN topic_id INTEGER')
    except: pass
    try: cursor.execute('ALTER TABLE active_sessions ADD COLUMN topic_id INTEGER')
    except: pass
    try: cursor.execute('ALTER TABLE tickets ADD COLUMN completed_at TEXT')
    except: pass
    
    # Auto cleanup orphaned sessions
    try:
        cursor.execute("DELETE FROM active_sessions WHERE ticket_id NOT IN (SELECT id FROM tickets WHERE status != 'Hoàn thành')")
    except:
        pass

    row_grp = cursor.execute("SELECT value FROM settings WHERE key='GROUP_IT_ID'").fetchone()
    row_sync = cursor.execute("SELECT value FROM settings WHERE key='LAST_SYNCED_GROUP_ID'").fetchone()
    if row_grp and not row_sync:
        cursor.execute("INSERT INTO settings (key, value) VALUES ('LAST_SYNCED_GROUP_ID', ?)", (row_grp[0],))
    
    conn.commit()
    conn.close()

def set_state(uid, step, temp_data=None):
    conn = connect_db()
    try:
        conn.execute("INSERT OR REPLACE INTO user_states_db (user_id, step, temp_data) VALUES (?, ?, ?)", (uid, step, temp_data))
        conn.commit()
    finally:
        conn.close()

def get_state(uid):
    conn = connect_db()
    try:
        row = conn.execute("SELECT step, temp_data FROM user_states_db WHERE user_id = ?", (uid,)).fetchone()
        return row if row else (None, None)
    finally:
        conn.close()

def clear_state(uid):
    conn = connect_db()
    try:
        conn.execute("DELETE FROM user_states_db WHERE user_id = ?", (uid,))
        conn.commit()
    finally:
        conn.close()

def get_config_from_db():
    conn = connect_db()
    try:
        cursor = conn.cursor()
        token_row = cursor.execute("SELECT value FROM settings WHERE key='BOT_TOKEN'").fetchone()
        group_row = cursor.execute("SELECT value FROM settings WHERE key='GROUP_IT_ID'").fetchone()
        offset_row = cursor.execute("SELECT value FROM settings WHERE key='TIME_OFFSET'").fetchone()
        t = token_row[0].strip() if token_row else None
        g = group_row[0].strip() if group_row else None
        o = int(offset_row[0]) if offset_row else 0
        return t, g, o
    finally:
        conn.close()