import sqlite3
import os

# Визначаємо шлях до бази даних для Railway Volume
if os.path.exists('/app/data'):
    DB_PATH = '/app/data/database.db'
else:
    DB_PATH = 'database.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_tech_mode():
    """Перевіряє режим технічних робіт для Middleware"""
    try:
        with get_db() as conn:
            res = conn.execute("SELECT status FROM settings WHERE key = 'tech_mode'").fetchone()
            return res['status'] == 1 if res else False
    except:
        return False

def init_db():
    with get_db() as conn:
        # Таблиця підписок
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                company TEXT,
                queue TEXT,
                UNIQUE(user_id, company, queue)
            )
        ''')
        # Таблиця налаштувань мови
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_prefs (
                user_id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'uk'
            )
        ''')
        # Таблиця графіків
        conn.execute('''
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT,
                date TEXT,
                queue TEXT,
                off_time TEXT,
                on_time TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Таблиця системних налаштувань (тех. роботи)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                status INTEGER DEFAULT 0
            )
        ''')
        conn.commit()
    print(f"✅ База даних ініціалізована за шляхом: {DB_PATH}")
