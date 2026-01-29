import asyncio
from datetime import datetime, timedelta
from database.db import get_db
from locales.strings import get_text

async def send_reminder(bot, user_id, company, queue, action, lang):
    text = get_text(lang, f'reminder_{action}', company=company, queue=queue)
    try:
        await bot.send_message(user_id, text)
    except Exception as e:
        print(f"Error sending reminder to {user_id}: {e}")

async def rebuild_jobs(bot, scheduler):
    scheduler.remove_all_jobs()
    
    with get_db() as conn:
        today = datetime.now().strftime('%Y-%m-%d')
        schedules = conn.execute("SELECT * FROM schedules WHERE date >= ?", (today,)).fetchall()
        
        for sched in schedules:
            date_str = sched['date']
            
            # ВИПРАВЛЕННЯ: замінюємо 24:00 на 23:59 для Python datetime
            off_time_str = sched['off_time'].replace('24:00', '23:59')
            on_time_str = sched['on_time'].replace('24:00', '23:59')
            
            try:
                off_t = datetime.strptime(f"{date_str} {off_time_str}", '%Y-%m-%d %H:%M')
                on_t = datetime.strptime(f"{date_str} {on_time_str}", '%Y-%m-%d %H:%M')
                
                users = conn.execute("SELECT u.user_id, p.language FROM users u "
                                     "JOIN user_prefs p ON u.user_id = p.user_id "
                                     "WHERE u.company=? AND u.queue=?", 
                                     (sched['company'], sched['queue'])).fetchall()
                
                for user in users:
                    # Нагадування за 10 хв до вимкнення
                    rem_off = off_t - timedelta(minutes=10)
                    if rem_off > datetime.now():
                        scheduler.add_job(send_reminder, 'date', run_date=rem_off, 
                                          args=[bot, user['user_id'], sched['company'], sched['queue'], 'off', user['language']])
                    
                    # Нагадування за 10 хв до ввімкнення
                    rem_on = on_t - timedelta(minutes=10)
                    if rem_on > datetime.now():
                        scheduler.add_job(send_reminder, 'date', run_date=rem_on, 
                                          args=[bot, user['user_id'], sched['company'], sched['queue'], 'on', user['language']])
            except ValueError as e:
                print(f"Помилка формату часу в черзі {sched['queue']}: {e}")
