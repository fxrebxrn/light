import sqlite3
import os

# Визначаємо шлях до бази даних
# Якщо ми в Railway і є папка /app/data, використовуємо її.
# Якщо ні — створюємо базу в корені проекту.
if os.path.exists('/app/data'):
    DB_PATH = '/app/data/database.db'
else:
    DB_PATH = 'database.db'

def get_db():
    """Створює підключення до бази даних з підтримкою словникового доступу"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Створює необхідні таблиці при першому запуску"""
    with get_db() as conn:
        # Таблиця підписок на черги
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                company TEXT,
                queue TEXT,
                UNIQUE(user_id, company, queue)
            )
        ''')
        
        # Таблиця налаштувань користувача (мова)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_prefs (
                user_id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'uk'
            )
        ''')
        
        # Таблиця самих графіків
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
        conn.commit()
    print(f"✅ База даних готова за шляхом: {DB_PATH}")
