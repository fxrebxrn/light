import asyncio
import pytz
from datetime import datetime, timedelta
from database.db import get_db
from locales.strings import get_text

# Примусовий часовий пояс
UA_TZ = pytz.timezone('Europe/Kyiv')

async def send_reminder(bot, user_id, company, queue, action, lang):
    """Надсилає нагадування користувачу"""
    text = get_text(lang, f'reminder_{action}', company=company, queue=queue)
    try:
        await bot.send_message(user_id, text)
    except Exception as e:
        print(f"Помилка відправки нагадування {user_id}: {e}")

async def rebuild_jobs(bot, scheduler):
    """Перебудовує всі завдання планувальника"""
    scheduler.remove_all_jobs()
    
    # Поточний час у Києві
    now_ua = datetime.now(UA_TZ)
    today_str = now_ua.strftime('%Y-%m-%d')
    
    with get_db() as conn:
        # Беремо графіки на сьогодні та майбутні дати
        schedules = conn.execute("SELECT * FROM schedules WHERE date >= ?", (today_str,)).fetchall()
        
        for sched in schedules:
            date_str = sched['date']
            # Заміна 24:00 для сумісності з datetime
            off_time_str = sched['off_time'].replace('24:00', '23:59')
            on_time_str = sched['on_time'].replace('24:00', '23:59')
            
            try:
                # Створюємо об'єкти часу з прив'язкою до Києва
                off_t = UA_TZ.localize(datetime.strptime(f"{date_str} {off_time_str}", '%Y-%m-%d %H:%M'))
                on_t = UA_TZ.localize(datetime.strptime(f"{date_str} {on_time_str}", '%Y-%m-%d %H:%M'))
                
                # Знаходимо підписаних юзерів
                users = conn.execute(
                    "SELECT u.user_id, p.language FROM users u "
                    "JOIN user_prefs p ON u.user_id = p.user_id "
                    "WHERE u.company=? AND u.queue=?", 
                    (sched['company'], sched['queue'])
                ).fetchall()
                
                for user in users:
                    # Нагадування про вимкнення (за 10 хв)
                    rem_off = off_t - timedelta(minutes=10)
                    if rem_off > now_ua:
                        scheduler.add_job(send_reminder, 'date', run_date=rem_off, 
                                          args=[bot, user['user_id'], sched['company'], sched['queue'], 'off', user['language']])
                    
                    # Нагадування про ввімкнення (за 10 хв)
                    rem_on = on_t - timedelta(minutes=10)
                    if rem_on > now_ua:
                        scheduler.add_job(send_reminder, 'date', run_date=rem_on, 
                                          args=[bot, user['user_id'], sched['company'], sched['queue'], 'on', user['language']])
            except Exception as e:
                print(f"Помилка планувальника для {date_str}: {e}")
    
    print(f"✅ Планувальник оновлено. Зараз у Києві: {now_ua.strftime('%H:%M:%S')}")
