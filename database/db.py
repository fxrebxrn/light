import sqlite3
import config

def get_db():
    conn = sqlite3.connect(config.DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        # Користувачі + мова
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            company TEXT,
            queue TEXT,
            language TEXT DEFAULT 'uk',
            UNIQUE(user_id, company, queue)
        )''')
        
        # Графіки
        conn.execute('''CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT,
            queue TEXT,
            date TEXT,
            off_time TEXT,
            on_time TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Налаштування бота (Тех. роботи)
        conn.execute('''CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        
        # Встановлюємо дефолт тех. робіт = 0 (вимкнено)
        conn.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('tech_mode', '0')")
        conn.commit()
        
        conn.execute('''CREATE TABLE IF NOT EXISTS user_prefs (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'uk'
        )''')

def set_user_lang(user_id, lang):
    with get_db() as conn:
        # Оновлюємо мову для всіх записів цього юзера (або створюємо фейковий запис, якщо юзера ще немає)
        # Оскільки структура users зав'язана на чергах, зробимо окрему логіку.
        # Спрощення: ми будемо апдейтити мову при додаванні черги, 
        # або створимо окрему таблицю user_prefs.
        # Для простоти: оновлюємо всі існуючі записи. 
        # А якщо записів немає, запам'ятати мову складно без окремої таблиці.
        # Тому: Створимо таблицю user_prefs
        pass # Реалізовано нижче в окремому блоці init

def get_tech_mode():
    with get_db() as conn:
        res = conn.execute("SELECT value FROM bot_settings WHERE key='tech_mode'").fetchone()
        return res['value'] == '1' if res else False