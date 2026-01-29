from aiogram import Dispatcher, types
from config import ADMIN_ID
from services.parser import parse_schedule_text
from database.db import get_db
from services.scheduler import rebuild_jobs
from locales.strings import get_text

# --- Notify Users Function ---
async def notify_users_about_update(bot, company, date_str, results):
    # Знаходимо унікальні черги, які оновилися
    updated_queues = set(r['queue'] for r in results)
    
    with get_db() as conn:
        for queue in updated_queues:
            # Знаходимо підписників цієї черги + їх мову
            users = conn.execute('''
                SELECT u.user_id, p.language 
                FROM users u
                LEFT JOIN user_prefs p ON u.user_id = p.user_id
                WHERE u.company = ? AND u.queue = ?
            ''', (company, queue)).fetchall()
            
            for user in users:
                lang = user['language'] or 'uk'
                text = get_text(lang, 'update_notify', company=company, queue=queue, date=date_str)
                try:
                    await bot.send_message(user['user_id'], text)
                except: pass

# --- Handlers ---
async def cmd_tech_on(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    with get_db() as conn:
        conn.execute("UPDATE bot_settings SET value='1' WHERE key='tech_mode'")
        conn.commit()
    await message.answer("🚧 TECH MODE: ON")

async def cmd_tech_off(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    with get_db() as conn:
        conn.execute("UPDATE bot_settings SET value='0' WHERE key='tech_mode'")
        conn.commit()
    await message.answer("✅ TECH MODE: OFF")

async def upload_schedule(message: types.Message, scheduler):
    if message.from_user.id != ADMIN_ID: return
    raw_text = message.text.replace('/upload', '').strip()
    
    company, date_str, data = parse_schedule_text(raw_text)
    
    if not company or not date_str:
        return await message.answer("❌ Формат: ДТЕК 29.01.2026 ...")
    
    with get_db() as conn:
        # Видаляємо старі записи за цю дату і компанію
        conn.execute("DELETE FROM schedules WHERE company = ? AND date = ?", (company, date_str))
        for item in data:
            conn.execute(
                "INSERT INTO schedules (company, queue, date, off_time, on_time) VALUES (?,?,?,?,?)",
                (item['company'], item['queue'], item['date'], item['off_time'], item['on_time'])
            )
        conn.commit()

    await rebuild_jobs(message.bot, scheduler)
    await notify_users_about_update(message.bot, company, date_str, data)
    await message.answer(f"✅ {company} ({date_str}) завантажено! Сповіщення розіслані.")

def register_handlers(dp: Dispatcher, scheduler):
    dp.register_message_handler(cmd_tech_on, commands=['techon'])
    dp.register_message_handler(cmd_tech_off, commands=['techoff'])
    dp.register_message_handler(lambda m: upload_schedule(m, scheduler), commands=['upload'])