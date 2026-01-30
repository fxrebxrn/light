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

def ensure_user_prefs_columns(conn):
    """Добавляет отсутствующие колонки для user_prefs (безопасно для существующей БД)."""
    try:
        existing = {row['name'] for row in conn.execute("PRAGMA table_info(user_prefs)").fetchall()}
    except Exception:
        existing = set()
    cols_to_add = {
        'notify_off': "INTEGER DEFAULT 1",
        'notify_on': "INTEGER DEFAULT 1",
        'notify_off_10': "INTEGER DEFAULT 1",
        'notify_on_10': "INTEGER DEFAULT 1",
    }
    for col, dtype in cols_to_add.items():
        if col not in existing:
            try:
                conn.execute(f"ALTER TABLE user_prefs ADD COLUMN {col} {dtype}")
            except Exception:
                # ALTER may fail in rare cases; ignore to keep app running
                pass

def get_user_settings(user_id):
    """Возвращает словарь с настройками пользователя (включая язык) и создаёт запись если её нет."""
    with get_db() as conn:
        # Убедимся, что таблица user_prefs содержит нужные колонки
        ensure_user_prefs_columns(conn)

        row = conn.execute("SELECT user_id, language, notify_off, notify_on, notify_off_10, notify_on_10 FROM user_prefs WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            return {
                'user_id': row['user_id'],
                'language': row['language'] or 'uk',
                'notify_off': 1 if row['notify_off'] is None else row['notify_off'],
                'notify_on': 1 if row['notify_on'] is None else row['notify_on'],
                'notify_off_10': 1 if row['notify_off_10'] is None else row['notify_off_10'],
                'notify_on_10': 1 if row['notify_on_10'] is None else row['notify_on_10'],
            }
        else:
            # Создаём запись с дефолтными значениями
            conn.execute("""
                INSERT OR REPLACE INTO user_prefs (user_id, language, notify_off, notify_on, notify_off_10, notify_on_10)
                VALUES (?, 'uk', 1, 1, 1, 1)
            """, (user_id,))
            conn.commit()
            return {
                'user_id': user_id,
                'language': 'uk',
                'notify_off': 1,
                'notify_on': 1,
                'notify_off_10': 1,
                'notify_on_10': 1,
            }

def set_user_setting(user_id, key, value):
    """Устанавливает одно поле настройки (key) для пользователя (INSERT или UPDATE)."""
    allowed = {'language', 'notify_off', 'notify_on', 'notify_off_10', 'notify_on_10'}
    if key not in allowed:
        raise ValueError("Not allowed setting key")
    with get_db() as conn:
        # Убедимся, что запись существует
        row = conn.execute("SELECT user_id FROM user_prefs WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            conn.execute("INSERT INTO user_prefs (user_id) VALUES (?)", (user_id,))
        conn.execute(f"UPDATE user_prefs SET {key} = ? WHERE user_id = ?", (value, user_id))
        conn.commit()

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
        # Таблиця налаштувань мови (расширим далее через ALTER если нужно)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_prefs (
                user_id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'uk'
            )
        ''')
        # Добавим недостающие колонки, если таблица уже существовала
        ensure_user_prefs_columns(conn)

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
