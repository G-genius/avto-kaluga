import os
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

from database import (
    get_connection,
    get_station_fuel_status,
)

load_dotenv()

MSK = timezone(timedelta(hours=3))

CHANNEL_ID = os.getenv("CHANNEL_ID")

if CHANNEL_ID:
    CHANNEL_ID = int(CHANNEL_ID)


def create_report():

    conn = get_connection()
    cursor = conn.cursor()

    # =====================================================
    # СТАТИСТИКА ЗА СЕГОДНЯ
    # =====================================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM fuel_reports
        WHERE date(created_at) = date('now','localtime')
    """)

    reports_today = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT user_id)
        FROM fuel_reports
        WHERE date(created_at) = date('now','localtime')
    """)

    users_today = cursor.fetchone()[0]

    cursor.execute("""
        SELECT
            id,
            display_name,
            brand
        FROM stations
        WHERE active = 1
        ORDER BY display_name
    """)

    stations = cursor.fetchall()

    conn.close()

    good = []
    bad = []
    no_data = []

    # =====================================================
    # АЗС
    # =====================================================

    for station_id, name, brand in stations:

        # Учитываем отметки только за последние 12 часов
        data = get_station_fuel_status(
            station_id=station_id,
            max_age_minutes=720
        )

        if not data:
            no_data.append(name)
            continue

        # =================================================
        # "ВСЕ ВИДЫ"
        # =================================================

        all_fuel_report = data.get("Все виды")

        if all_fuel_report:

            all_fuel_status = all_fuel_report.get("status")
            all_fuel_time = all_fuel_report.get("created_at")

        else:

            all_fuel_status = None
            all_fuel_time = None

        # =================================================
        # СОСТОЯНИЕ ТОПЛИВА
        # =================================================

        fuel_status = {
            "АИ-92": None,
            "АИ-95": None,
            "АИ-98/100": None,
            "Дизель": None,
        }

        fuel_source = {
            "АИ-92": None,
            "АИ-95": None,
            "АИ-98/100": None,
            "Дизель": None,
        }

        # =================================================
        # "ВСЕ ВИДЫ" → ЕСТЬ
        # =================================================

        if all_fuel_status == "🟢 Есть":

            for fuel in [
                "АИ-92",
                "АИ-95",
                "Дизель"
            ]:

                fuel_status[fuel] = "🟢 Есть"
                fuel_source[fuel] = all_fuel_report

        # =================================================
        # "ВСЕ ВИДЫ" → НЕТ
        # =================================================

        elif all_fuel_status == "🔴 Нет":

            for fuel in [
                "АИ-92",
                "АИ-95",
                "Дизель"
            ]:

                fuel_status[fuel] = "🔴 Нет"
                fuel_source[fuel] = all_fuel_report

        # =================================================
        # КОНКРЕТНЫЕ ОТМЕТКИ
        # Более свежая отметка перебивает "Все виды"
        # =================================================

        for fuel in [
            "АИ-92",
            "АИ-95",
            "АИ-98/100",
            "Дизель"
        ]:

            item = data.get(fuel)

            if not item:
                continue

            specific_time = item.get("created_at")

            if all_fuel_time:

                if (
                    specific_time
                    and specific_time > all_fuel_time
                ):

                    fuel_status[fuel] = item.get("status")
                    fuel_source[fuel] = item

            else:

                fuel_status[fuel] = item.get("status")
                fuel_source[fuel] = item

        # =================================================
        # КАРТОЧКА АЗС
        # =================================================

        station_text = (
            f"⛽ <b>{name}</b>\n"
        )

        if brand:

            station_text += (
                f"🏷 {brand}\n"
            )

        has_good = False
        has_bad = False
        has_conflict = False

        conflict_fuels = []

        fuel_order = [
            "АИ-92",
            "АИ-95",
            "АИ-98/100",
            "Дизель"
        ]

        latest_time = None
        latest_queue = None
        latest_comment = None

        # =================================================
        # ТОПЛИВО
        # =================================================

        for fuel in fuel_order:

            status = fuel_status[fuel]

            if status is None:
                continue

            item = fuel_source[fuel]

            if not item:
                continue

            yes_count = item.get("yes_count", 0)
            no_count = item.get("no_count", 0)

            # -------------------------------------------------
            # ПРОТИВОРЕЧИВЫЕ ДАННЫЕ
            # -------------------------------------------------

            if yes_count > 0 and no_count > 0:

                station_text += (
                    f"• {fuel} ⚠️ "
                    f"противоречивые данные\n"
                )

                has_conflict = True
                conflict_fuels.append(fuel)

                # Даже конфликтная отметка может быть
                # самой свежей и содержать очередь/комментарий
                item_time = item.get("created_at")

                if (
                    item_time
                    and (
                        latest_time is None
                        or item_time > latest_time
                    )
                ):

                    latest_time = item_time
                    latest_queue = item.get("queue")
                    latest_comment = item.get("comment")

                continue

            # -------------------------------------------------
            # ПОСЛЕДНЯЯ ОТМЕТКА
            # -------------------------------------------------

            item_time = item.get("created_at")

            if (
                item_time
                and (
                    latest_time is None
                    or item_time > latest_time
                )
            ):

                latest_time = item_time
                latest_queue = item.get("queue")
                latest_comment = item.get("comment")

            # -------------------------------------------------
            # ЕСТЬ
            # -------------------------------------------------

            if status == "🟢 Есть":

                station_text += (
                    f"• {fuel} 🟢 есть\n"
                )

                has_good = True

            # -------------------------------------------------
            # НЕТ
            # -------------------------------------------------

            elif status == "🔴 Нет":

                station_text += (
                    f"• {fuel} 🔴 нет\n"
                )

                has_bad = True

        # =================================================
        # ВРЕМЯ
        # =================================================

        if latest_time:

            try:
                display_time = latest_time[11:16]
            except Exception:
                display_time = str(latest_time)

            station_text += (
                f"🕐 Последняя отметка: "
                f"{display_time}\n"
            )

        # =================================================
        # ОЧЕРЕДЬ
        # =================================================

        if latest_queue:

            station_text += (
                f"🚗 Очередь: {latest_queue}\n"
            )

        # =================================================
        # КОММЕНТАРИЙ
        # =================================================

        if latest_comment:

            station_text += (
                f"💬 {latest_comment}\n"
            )

        station_text += "\n"

        # =================================================
        # КАТЕГОРИЯ АЗС
        # =================================================

        if has_bad:

            bad.append(station_text)

        elif has_conflict and not has_good:

            bad.append(station_text)

        elif has_good:

            good.append(station_text)

        elif has_conflict:

            good.append(station_text)

        else:

            no_data.append(name)

    # =====================================================
    # ФОРМИРУЕМ ОТЧЁТ
    # =====================================================

    now = datetime.now(MSK)

    report = [

        "🚗 <b>АвтоКалуга</b>",

        "⛽ <b>Ситуация с топливом</b>",

        "",

        f"🕐 Обновлено: {now.strftime('%H:%M')}",

        "",

        "📊 <b>Сегодня:</b>",

        f"👥 Отметок от водителей: {users_today}",

        f"📝 Всего проверок: {reports_today}",

        "",
    ]

    # =====================================================
    # ЕСТЬ ТОПЛИВО
    # =====================================================

    if good:

        report.append(
            "🟢 <b>ЕСТЬ ТОПЛИВО</b>"
        )

        report.append("")

        for item in good:
            report.append(item)

    # =====================================================
    # ПРОБЛЕМЫ
    # =====================================================

    if bad:

        report.append(
            "🔴 <b>ПРОБЛЕМЫ</b>"
        )

        report.append("")

        for item in bad:
            report.append(item)

    # =====================================================
    # НЕТ СВЕЖИХ ДАННЫХ
    # =====================================================

    if no_data:

        no_data = sorted(set(no_data))

        report.append(
            "⚪ <b>Нет свежих данных:</b>"
        )

        report.append(
            " • ".join(no_data[:12])
        )

    # =====================================================
    # ПОДВАЛ
    # =====================================================

    report.append("")

    report.append(
        "🕐 Учитываются отметки "
        "за последние 12 часов."
    )

    report.append(
        "ℹ️ Данные от автомобилистов."
    )

    return "\n".join(report)


# =========================================================
# ОТПРАВКА ОТЧЁТА
# =========================================================

async def send_report(bot):

    if not CHANNEL_ID:

        print("⚠️ CHANNEL_ID не задан")

        return

    text = create_report()

    # =====================================================
    # ССЫЛКИ
    # =====================================================

    text += """

━━━━━━━━━━━━━━

🚗 <b>АвтоКалуга</b>

⛽ <a href="https://t.me/AvtoKalugaBot">
Сообщить о наличии топлива
</a>

📢 <a href="https://t.me/auto_kaluga_40">
Наш Telegram-канал
</a>

💬 <a href="https://t.me/+IqwbevSSwas2MTEy">
Чат автомобилистов
</a>

🤝 Сделайте отметку после заправки —
помогите другим водителям.
"""

    # =====================================================
    # TELEGRAM MAX 4096
    # =====================================================

    MAX_LENGTH = 4000

    parts = []

    while len(text) > MAX_LENGTH:

        split_at = text.rfind(
            "\n",
            0,
            MAX_LENGTH
        )

        if split_at == -1:

            split_at = MAX_LENGTH

        parts.append(
            text[:split_at]
        )

        text = text[
            split_at:
        ].lstrip()

    if text:

        parts.append(text)

    # =====================================================
    # ОТПРАВКА
    # =====================================================

    for part in parts:

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=part,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    print("📢 Отчёт отправлен")