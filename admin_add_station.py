from aiogram import Dispatcher
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from database import get_connection


admin_add_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="❌ Отмена")
        ]
    ],
    resize_keyboard=True,
)


add_station_state = {}


async def start_add_station(message: Message):

    user_id = message.from_user.id

    add_station_state[user_id] = {
        "step": "name"
    }

    await message.answer(
        "⛽ Введите название АЗС:",
        reply_markup=admin_add_keyboard,
    )


async def add_station_handler(message: Message):

    user_id = message.from_user.id

    if user_id not in add_station_state:
        return

    text = message.text


    if text == "❌ Отмена":

        add_station_state.pop(
            user_id,
            None
        )

        await message.answer(
            "❌ Добавление отменено."
        )

        return


    step = add_station_state[user_id]["step"]


    # название

    if step == "name":

        add_station_state[user_id]["name"] = text

        add_station_state[user_id]["step"] = "brand"

        await message.answer(
            "🏷 Введите бренд:"
        )

        return


    # бренд

    if step == "brand":

        add_station_state[user_id]["brand"] = text

        add_station_state[user_id]["step"] = "address"

        await message.answer(
            "📍 Введите адрес:"
        )

        return


    # адрес

    if step == "address":

        add_station_state[user_id]["address"] = text

        add_station_state[user_id]["step"] = "lat"

        await message.answer(
            "🌍 Введите широту:"
        )

        return


    # широта

    if step == "lat":

        try:

            latitude = float(text)

        except:

            await message.answer(
                "Введите число.\n"
                "Пример: 54.522087"
            )

            return


        add_station_state[user_id]["latitude"] = latitude

        add_station_state[user_id]["step"] = "lon"


        await message.answer(
            "🌍 Введите долготу:"
        )

        return


    # долгота

    if step == "lon":

        try:

            longitude = float(text)

        except:

            await message.answer(
                "Введите число.\n"
                "Пример: 36.284625"
            )

            return


        data = add_station_state[user_id]


        conn = get_connection()

        cursor = conn.cursor()


        cursor.execute(
            """
            INSERT INTO stations
            (
                display_name,
                brand,
                address,
                latitude,
                longitude,
                active
            )
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (
                data["name"],
                data["brand"],
                data["address"],
                data["latitude"],
                longitude,
            )
        )


        conn.commit()

        conn.close()


        await message.answer(
            "✅ АЗС добавлена!\n\n"
            f"⛽ {data['name']}\n"
            f"🏷 {data['brand']}\n"
            f"📍 {data['address']}\n"
            f"🌍 {data['latitude']}, {longitude}"
        )


        add_station_state.pop(
            user_id,
            None
        )

        return



def register_admin_add_handlers(dp: Dispatcher):

    dp.message.register(
        add_station_handler,
        lambda message:
        message.from_user.id in add_station_state
    )