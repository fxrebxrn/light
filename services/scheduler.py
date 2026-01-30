from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import pytz
from database.db import get_db

# 🔧 ВАЖНО: send_notify лежит в main.py
from main import send_notify

UA_TZ = pytz.timezone("Europe/Kyiv")


async def rebuild_jobs(bot, scheduler: AsyncIOScheduler):
    scheduler.remove_all_jobs()

    with get_db() as conn:
        schedules = conn.execute(
            "SELECT * FROM schedule"
        ).fetchall()

    for row in schedules:
        try:
            company = row["company"]
            queue = row["queue"]
            date_str = row["date"]
            off_time = row["off_time"]
            on_time = row["on_time"]

            off_dt = datetime.strptime(
                f"{date_str} {off_time}", "%Y-%m-%d %H:%M"
            )
            off_dt = UA_TZ.localize(off_dt)

            on_dt = datetime.strptime(
                f"{date_str} {on_time}", "%Y-%m-%d %H:%M"
            )
            on_dt = UA_TZ.localize(on_dt)

            notify_dt = off_dt - timedelta(minutes=10)

            now = datetime.now(UA_TZ)

            if notify_dt > now:
                scheduler.add_job(
                    send_notify,
                    "date",
                    run_date=notify_dt,
                    args=[bot, company, queue, "before"],
                )

            if off_dt > now:
                scheduler.add_job(
                    send_notify,
                    "date",
                    run_date=off_dt,
                    args=[bot, company, queue, "off"],
                )

            if on_dt > now:
                scheduler.add_job(
                    send_notify,
                    "date",
                    run_date=on_dt,
                    args=[bot, company, queue, "on"],
                )

        except Exception as e:
            print("Error scheduling jobs for schedule row:", dict(row))
            print(e)
