import math

from aiogram import Dispatcher
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from database import (
    get_connection,
    get_station_fuel_status,
)


location_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="📍 Отправить местоположение",
                request_location=True
            )
        ],
        [
            KeyboardButton(
                text="⬅️ Назад"
            )
        ]
    ],
    resize_keyboard=True,
)


def distance_km(
    lat1,
    lon1,
    lat2,
    lon2
):

    R = 6371

    d_lat = math.radians(
        lat2 - lat1
    )

    d_lon = math.radians(
        lon2 - lon1
    )


    a = (
        math.sin(d_lat / 2) ** 2
        +
        math.cos(math.radians(lat1))
        *
        math.cos(math.radians(lat2))
        *
        math.sin(d_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1-a)
    )

    return R * c



async def start_nearby(
    message: Message
):

    await message.answer(
        "📍 Отправьте свою геопозицию,\n"
        "и я покажу ближайшие АЗС.",
        reply_markup=location_keyboard
    )



async def location_handler(
    message: Message
):

    if not message.location:
        return


    user_lat = message.location.latitude
    user_lon = message.location.longitude


    conn = get_connection()
    cursor = conn.cursor()


    cursor.execute("""
        SELECT
            display_name,
            brand,
            latitude,
            longitude
        FROM stations
        WHERE active = 1
        AND latitude IS NOT NULL
        AND longitude IS NOT NULL
    """)


    stations = cursor.fetchall()

    conn.close()



    result = []


    for (
        name,
        brand,
        lat,
        lon
    ) in stations:


        km = distance_km(
            user_lat,
            user_lon,
            lat,
            lon
        )


        result.append(
            (
                km,
                name,
                brand
            )
        )



    result.sort(
        key=lambda x: x[0]
    )


    if not result:

        await message.answer(
            "⚠️ Рядом АЗС не найдены."
        )

        return



    text = [
        "🚗 <b>Ближайшие АЗС:</b>\n"
    ]


    for (
        km,
        name,
        brand
    ) in result[:5]:


        text.append(
            f"⛽ <b>{name}</b>"
        )


        if brand:

            text.append(
                f"🏷 {brand}"
            )


        text.append(
            f"📍 {km:.1f} км"
        )


        fuels = get_station_fuel_status(
            name
        )


        for fuel, data in fuels.items():

            text.append(
                f"{fuel}: {data['status']}"
            )


        text.append("")



    await message.answer(
        "\n".join(text),
        parse_mode="HTML",
    )



def register_nearby_handlers(
    dp: Dispatcher
):

    dp.message.register(
        location_handler,
        lambda message:
        message.location is not None
    )