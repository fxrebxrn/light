from datetime import datetime, timedelta
from database.db import get_db

async def send_notification(bot, user_id, text):
    try:
        await bot.send_message(user_id, text)
    except Exception:
        pass

async def rebuild_jobs(bot, scheduler):
    scheduler.remove_all_jobs()
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    
    with get_db() as conn:
        schedules = conn.execute("SELECT * FROM schedules WHERE date >= ?", (today,)).fetchall()
        
        for sched in schedules:
            company, queue, date_str = sched['company'], sched['queue'], sched['date']
            off_t = datetime.strptime(f"{date_str} {sched['off_time']}", '%Y-%m-%d %H:%M')
            on_t = datetime.strptime(f"{date_str} {sched['on_time']}", '%Y-%m-%d %H:%M')

            # Беремо юзерів з черги
            users = conn.execute("SELECT user_id FROM users WHERE company = ? AND queue = ?", (company, queue)).fetchall()

            for user in users:
                uid = user['user_id']
                # Тут можна додати логіку мови для кожного юзера,
                # але для швидкодії scheduler часто шле універсальні повідомлення або парсить їх окремо.
                # Для прикладу - простий текст.
                events = [
                    (off_t - timedelta(minutes=10), f"⚠️ {queue} ({company}): 10 хв до ВІДКЛЮЧЕННЯ"),
                    (off_t, f"🔴 {queue} ({company}): Світло ВІДКЛЮЧЕНО"),
                    (on_t - timedelta(minutes=10), f"⚠️ {queue} ({company}): 10 хв до ВМКНЕННЯ"),
                    (on_t, f"🟢 {queue} ({company}): Світло ВМКНУТО")
                ]
                for run_time, text in events:
                    if run_time > now:
                        scheduler.add_job(send_notification, 'date', run_date=run_time, args=[bot, uid, text])