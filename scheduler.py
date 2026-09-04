import asyncio
from datetime import datetime, timedelta, timezone

from report_channel import send_report
from auto_posts import send_auto_post


MSK = timezone(timedelta(hours=3))


SCHEDULE = [
    (7, "report"),
    (9, "post"),
    (12, "report"),
    (14, "post"),
    (15, "report"),
    (19, "report"),
    (20, "post"),
]


async def start_scheduler(bot):

    while True:

        now = datetime.now(MSK)

        next_run = None
        next_action = None

        for hour, action in SCHEDULE:

            candidate = now.replace(
                hour=hour,
                minute=0,
                second=0,
                microsecond=0
            )

            if candidate > now:

                next_run = candidate
                next_action = action

                break

        if next_run is None:

            hour, action = SCHEDULE[0]

            next_run = (
                now.replace(
                    hour=hour,
                    minute=0,
                    second=0,
                    microsecond=0
                )
                + timedelta(days=1)
            )

            next_action = action

        wait_seconds = (
            next_run - now
        ).total_seconds()

        action_name = (
            "топливный отчёт"
            if next_action == "report"
            else "автопост"
        )

        print(
            f"📅 Следующий запуск: "
            f"{next_run.strftime('%d.%m.%Y %H:%M')} "
            f"— {action_name}"
        )

        await asyncio.sleep(wait_seconds)

        try:

            if next_action == "report":

                await send_report(bot)

                print(
                    f"✅ Автоматический отчёт отправлен: "
                    f"{datetime.now(MSK).strftime('%d.%m.%Y %H:%M')}"
                )

            elif next_action == "post":

                # Номер слота автопоста:
                # 09:00 → 0
                # 14:00 → 1
                # 20:00 → 2

                post_slots = {
                    9: 0,
                    14: 1,
                    20: 2,
                }

                slot_index = post_slots.get(
                    next_run.hour,
                    0
                )

                # 3 разных поста каждый день.
                # День меняет стартовую позицию,
                # поэтому контент постепенно ротируется.

                day_index = (
                    datetime.now(MSK).toordinal()
                    * 3
                )

                post_index = (
                    day_index + slot_index
                ) % 20

                await send_auto_post(
                    bot,
                    post_index
                )

                print(
                    f"✅ Автопост отправлен: "
                    f"{datetime.now(MSK).strftime('%d.%m.%Y %H:%M')} "
                    f"(№{post_index + 1})"
                )

        except Exception as e:

            print(
                "❌ Ошибка планировщика:",
                e
            )