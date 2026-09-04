from aiogram import Dispatcher
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from database import get_connection


edit_state = {}


edit_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="❌ Отмена")
        ]
    ],
    resize_keyboard=True,
)


def get_station_list():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            display_name,
            brand
        FROM stations
        ORDER BY display_name
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows



async def start_edit_station(message: Message):

    user_id = message.from_user.id

    stations = get_station_list()

    if not stations:

        await message.answer(
            "⛽ АЗС нет в базе."
        )

        return


    result = [
        "✏️ Введите ID АЗС:"
    ]


    for (
        station_id,
        name,
        brand
    ) in stations:

        result.append(
            f"{station_id}. {name} — {brand}"
        )


    edit_state[user_id] = {
        "step": "select"
    }


    await message.answer(
        "\n".join(result),
        reply_markup=edit_keyboard,
    )



async def edit_station_handler(message: Message):

    user_id = message.from_user.id


    if user_id not in edit_state:
        return


    text = message.text


    if text == "❌ Отмена":

        edit_state.pop(
            user_id,
            None
        )

        await message.answer(
            "❌ Редактирование отменено."
        )

        return



    step = edit_state[user_id]["step"]



    # выбор ID

    if step == "select":

        try:

            station_id = int(text)

        except:

            await message.answer(
                "Введите номер АЗС."
            )

            return



        conn = get_connection()
        cursor = conn.cursor()


        cursor.execute(
            """
            SELECT
                display_name,
                brand,
                address,
                latitude,
                longitude
            FROM stations
            WHERE id=?
            """,
            (
                station_id,
            )
        )


        station = cursor.fetchone()

        conn.close()


        if not station:

            await message.answer(
                "❌ Такая АЗС не найдена."
            )

            return


        edit_state[user_id] = {
            "step": "name",
            "id": station_id
        }


        await message.answer(
            f"⛽ Текущая АЗС:\n\n"
            f"{station[0]}\n"
            f"{station[1]}\n"
            f"{station[2]}\n\n"
            "Введите новое название:"
        )


        return



    # название

    if step == "name":

        edit_state[user_id]["name"] = text
        edit_state[user_id]["step"] = "brand"


        await message.answer(
            "Введите новый бренд:"
        )

        return



    # бренд

    if step == "brand":

        edit_state[user_id]["brand"] = text
        edit_state[user_id]["step"] = "address"


        await message.answer(
            "Введите новый адрес:"
        )

        return



    # адрес

    if step == "address":

        edit_state[user_id]["address"] = text
        edit_state[user_id]["step"] = "lat"


        await message.answer(
            "Введите новую широту:"
        )

        return



    # широта

    if step == "lat":

        try:

            lat = float(text)

        except:

            await message.answer(
                "Введите число."
            )

            return


        edit_state[user_id]["lat"] = lat
        edit_state[user_id]["step"] = "lon"


        await message.answer(
            "Введите новую долготу:"
        )

        return



    # долгота

    if step == "lon":

        try:

            lon = float(text)

        except:

            await message.answer(
                "Введите число."
            )

            return


        data = edit_state[user_id]


        conn = get_connection()
        cursor = conn.cursor()


        cursor.execute(
            """
            UPDATE stations

            SET
                display_name=?,
                brand=?,
                address=?,
                latitude=?,
                longitude=?

            WHERE id=?
            """,
            (
                data["name"],
                data["brand"],
                data["address"],
                data["lat"],
                lon,
                data["id"],
            )
        )


        conn.commit()
        conn.close()



        await message.answer(
            "✅ АЗС обновлена!\n\n"
            f"⛽ {data['name']}\n"
            f"🏷 {data['brand']}\n"
            f"📍 {data['address']}"
        )


        edit_state.pop(
            user_id,
            None
        )

        return




def register_admin_edit_handlers(dp: Dispatcher):

    dp.message.register(
        edit_station_handler,
        lambda message:
        message.from_user.id in edit_state
    )