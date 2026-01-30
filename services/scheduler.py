import asyncio
import pytz
from datetime import datetime, timedelta
from database.db import get_db
from locales.strings import get_text

# Примусовий часовий пояс
UA_TZ = pytz.timezone('Europe/Kyiv')

async def send_reminder(bot, user_id, company, queue, action, lang):
    """Надсилає нагадування користувачу"""
    # action может быть:
    #  - 'off' / 'on'         -> reminder за 10 минут (ключ: reminder_off / reminder_on)
    #  - 'off_now' / 'on_now' -> уведомление в момент события (ключ: off_now / on_now)
    if action in ('off', 'on'):
        key = f'reminder_{action}'
    else:
        key = action  # off_now / on_now
    text = get_text(lang, key, company=company, queue=queue)
    try:
        await bot.send_message(user_id, text)
    except Exception as e:
        print(f"Помилка відправки нагадування {user_id}: {e}")

async def rebuild_jobs(bot, scheduler):
    """Перебудовує всі завдання планувальника"""
    try:
        scheduler.remove_all_jobs()
    except Exception:
        pass

    # Поточний час у Києві
    now_ua = datetime.now(UA_TZ)
    today_str = now_ua.strftime('%Y-%m-%d')

    with get_db() as conn:
        # Беремо графіки на сьогодні та майбутні дати
        schedules = conn.execute("SELECT * FROM schedules WHERE date >= ?", (today_str,)).fetchall()

        for sched in schedules:
            date_str = sched['date']
            # Заміна 24:00 для сумісності з datetime
            off_time_str = (sched.get('off_time') or '').replace('24:00', '23:59')
            on_time_str = (sched.get('on_time') or '').replace('24:00', '23:59')

            try:
                # Створюємо об'єкти часу з прив'язкою до Києва
                off_dt_naive = datetime.strptime(f"{date_str} {off_time_str}", '%Y-%m-%d %H:%M')
                on_dt_naive = datetime.strptime(f"{date_str} {on_time_str}", '%Y-%m-%d %H:%M')
                off_t = UA_TZ.localize(off_dt_naive)
                on_t = UA_TZ.localize(on_dt_naive)

                # Знаходимо підписаних юзерів + їх prefs (используем COALESCE чтобы дефолт был 1)
                users = conn.execute(
                    "SELECT u.user_id, COALESCE(p.language, 'uk') as language, "
                    "COALESCE(p.notify_off, 1) as notify_off, COALESCE(p.notify_on, 1) as notify_on, "
                    "COALESCE(p.notify_off_10, 1) as notify_off_10, COALESCE(p.notify_on_10, 1) as notify_on_10 "
                    "FROM users u LEFT JOIN user_prefs p ON u.user_id = p.user_id "
                    "WHERE u.company=? AND u.queue=?",
                    (sched['company'], sched['queue'])
                ).fetchall()

                for user in users:
                    user_id = user['user_id']
                    lang = user['language'] or 'uk'

                    # Нагадування про вимкнення (за 10 хв)
                    rem_off = off_t - timedelta(minutes=10)
                    if rem_off > now_ua and int(user['notify_off_10']) == 1:
                        scheduler.add_job(send_reminder, 'date', run_date=rem_off,
                                          args=[bot, user_id, sched['company'], sched['queue'], 'off', lang])

                    # Уведомление в момент вимкнення
                    if off_t > now_ua and int(user['notify_off']) == 1:
                        scheduler.add_job(send_reminder, 'date', run_date=off_t,
                                          args=[bot, user_id, sched['company'], sched['queue'], 'off_now', lang])

                    # Нагадування про ввімкнення (за 10 хв)
                    rem_on = on_t - timedelta(minutes=10)
                    if rem_on > now_ua and int(user['notify_on_10']) == 1:
                        scheduler.add_job(send_reminder, 'date', run_date=rem_on,
                                          args=[bot, user_id, sched['company'], sched['queue'], 'on', lang])

                    # Уведомление в момент ввімкнення
                    if on_t > now_ua and int(user['notify_on']) == 1:
                        scheduler.add_job(send_reminder, 'date', run_date=on_t,
                                          args=[bot, user_id, sched['company'], sched['queue'], 'on_now', lang])

            except Exception as e:
                print("Error scheduling jobs for", sched, e)
