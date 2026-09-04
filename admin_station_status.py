from aiogram import Dispatcher
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from database import get_connection


status_state = {}


status_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="❌ Отмена")
        ]
    ],
    resize_keyboard=True,
)


def get_stations():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            display_name,
            brand,
            active
        FROM stations
        ORDER BY display_name
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


async def start_station_status(message: Message):

    user_id = message.from_user.id

    stations = get_stations()

    if not stations:
        await message.answer(
            "⛽ АЗС в базе пока нет."
        )
        return

    result = [
        "🟢/🔴 Статус АЗС\n",
        "Введите ID АЗС:"
    ]

    for (
        station_id,
        name,
        brand,
        active
    ) in stations:

        if active:
            status = "🟢 активна"
        else:
            status = "🔴 отключена"

        result.append(
            f"{station_id}. {name} — {brand or 'Без бренда'} "
            f"({status})"
        )

    status_state[user_id] = {
        "step": "select"
    }

    await message.answer(
        "\n".join(result),
        reply_markup=status_keyboard,
    )


async def station_status_handler(message: Message):

    user_id = message.from_user.id

    if user_id not in status_state:
        return

    text = message.text

    if text == "❌ Отмена":

        status_state.pop(
            user_id,
            None
        )

        await message.answer(
            "❌ Изменение статуса отменено."
        )

        return

    step = status_state[user_id]["step"]

    if step == "select":

        try:
            station_id = int(text)

        except ValueError:

            await message.answer(
                "Введите числовой ID АЗС."
            )

            return

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                display_name,
                brand,
                active
            FROM stations
            WHERE id = ?
            """,
            (station_id,)
        )

        station = cursor.fetchone()

        conn.close()

        if not station:

            await message.answer(
                "❌ АЗС с таким ID не найдена."
            )

            return

        name, brand, active = station

        status_state[user_id] = {
            "step": "confirm",
            "station_id": station_id,
            "name": name,
            "brand": brand,
            "active": active,
        }

        current_status = (
            "🟢 Активна"
            if active
            else "🔴 Отключена"
        )

        new_status = (
            "🔴 Отключить"
            if active
            else "🟢 Включить"
        )

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(
                        text=new_status
                    )
                ],
                [
                    KeyboardButton(
                        text="❌ Отмена"
                    )
                ],
            ],
            resize_keyboard=True,
        )

        await message.answer(
            f"⛽ {name}\n"
            f"🏷 {brand or 'Без бренда'}\n\n"
            f"Сейчас: {current_status}\n\n"
            f"Нажмите «{new_status}».",
            reply_markup=keyboard,
        )

        return

    if step == "confirm":

        data = status_state[user_id]

        if text not in [
            "🔴 Отключить",
            "🟢 Включить",
        ]:

            await message.answer(
                "Используйте кнопку выше."
            )

            return

        if text == "🟢 Включить":
            new_active = 1
            new_status = "🟢 Активна"
        else:
            new_active = 0
            new_status = "🔴 Отключена"

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE stations
            SET active = ?
            WHERE id = ?
            """,
            (
                new_active,
                data["station_id"],
            )
        )

        conn.commit()
        conn.close()

        await message.answer(
            "✅ Статус АЗС изменён!\n\n"
            f"⛽ {data['name']}\n"
            f"🏷 {data['brand'] or 'Без бренда'}\n"
            f"Статус: {new_status}"
        )

        status_state.pop(
            user_id,
            None
        )

        return


def register_station_status_handlers(dp: Dispatcher):

    dp.message.register(
        station_status_handler,
        lambda message:
        message.from_user.id in status_state
    )