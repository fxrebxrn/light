# --- ВАЖНО: ИМПОРТЫ В НАЧАЛЕ ФАЙЛА ---
from aiogram import Dispatcher, types
from aiogram.utils.callback_data import CallbackData
from database.db import get_db, get_user_settings, set_user_setting
import config
from locales.strings import get_text
from datetime import datetime
import pytz

# Часовой пояс Киева
UA_TZ = pytz.timezone('Europe/Kyiv')

cb_lang = CallbackData("lang", "code")
cb_menu = CallbackData("menu", "action", "val")
cb_sched = CallbackData("sched", "comp", "queue")
cb_notify = CallbackData("notify", "key", "val")

# --- УДАЛЕНИЕ ПОДПИСКИ (ИСПРАВЛЕНО) ---
async def delete_sub(call: types.CallbackQuery):
    try:
        sub_id = call.data.split("_", 1)[1]
    except Exception:
        await call.answer("Невірні дані", show_alert=True)
        return

    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id=?", (sub_id,))
        conn.commit()

    # 🔥 ВОТ ЭТО ИСПРАВЛЕНИЕ
    from main import scheduler
    from services.scheduler import rebuild_jobs
    await rebuild_jobs(call.bot, scheduler)

    await call.answer("Видалено", show_alert=True)
    try:
        await call.message.delete()
    except Exception:
        pass


async def send_reminder(bot, user_id, company, queue, action, lang):
    """Отправляет напоминание пользователю."""
    # action может быть: 'off'/'on' (reminder за 10 минут) или 'off_now'/'on_now' (уведомление в момент события)
    if action in ('off', 'on'):
        key = f'reminder_{action}'
    else:
        key = action  # off_now / on_now
    text = get_text(lang, key, company=company, queue=queue)
    try:
        await bot.send_message(user_id, text)
    except Exception as e:
        print(f"Ошибка отправки напоминания {user_id}: {e}")

async def rebuild_jobs(bot, scheduler):
    """Перестраивает все задания планировщика."""
    try:
        scheduler.remove_all_jobs()
    except Exception:
        pass

    now_ua = datetime.now(UA_TZ)
    today_str = now_ua.strftime('%Y-%m-%d')

    with get_db() as conn:
        schedules = conn.execute("SELECT * FROM schedules WHERE date >= ?", (today_str,)).fetchall()

        for sched in schedules:
            try:
                date_str = sched['date']
                off_time_raw = sched['off_time'] or ''
                on_time_raw = sched['on_time'] or ''

                # Заменяем '24:00' на '23:59' для корректного парсинга
                off_time_str = off_time_raw.replace('24:00', '23:59')
                on_time_str = on_time_raw.replace('24:00', '23:59')

                # Парсим datetime (в локальном Kyiv tz)
                off_dt_naive = datetime.strptime(f"{date_str} {off_time_str}", '%Y-%m-%d %H:%M')
                on_dt_naive = datetime.strptime(f"{date_str} {on_time_str}", '%Y-%m-%d %H:%M')
                off_t = UA_TZ.localize(off_dt_naive)
                on_t = UA_TZ.localize(on_dt_naive)

                # Получаем подписанных пользователей вместе с их prefs
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

                    # Напоминание о выключении за 10 минут
                    rem_off = off_t - timedelta(minutes=10)
                    if rem_off > now_ua and int(user['notify_off_10']) == 1:
                        scheduler.add_job(send_reminder, 'date', run_date=rem_off,
                                          args=[bot, user_id, sched['company'], sched['queue'], 'off', lang])

                    # Уведомление в момент выключения
                    if off_t > now_ua and int(user['notify_off']) == 1:
                        scheduler.add_job(send_reminder, 'date', run_date=off_t,
                                          args=[bot, user_id, sched['company'], sched['queue'], 'off_now', lang])

                    # Напоминание о включении за 10 минут
                    rem_on = on_t - timedelta(minutes=10)
                    if rem_on > now_ua and int(user['notify_on_10']) == 1:
                        scheduler.add_job(send_reminder, 'date', run_date=rem_on,
                                          args=[bot, user_id, sched['company'], sched['queue'], 'on', lang])

                    # Уведомление в момент включения
                    if on_t > now_ua and int(user['notify_on']) == 1:
                        scheduler.add_job(send_reminder, 'date', run_date=on_t,
                                          args=[bot, user_id, sched['company'], sched['queue'], 'on_now', lang])

            except Exception as e:
                # печатаем информацию, чтобы не ломать запуск
                print("Error scheduling jobs for schedule row:", dict(sched))
                print(e)

