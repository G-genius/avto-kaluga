import asyncio
import math
import os
from datetime import datetime, timedelta, timezone

MSK = timezone(timedelta(hours=3))

def local_time():
    return datetime.now(MSK)

from dotenv import load_dotenv

load_dotenv()

from scheduler import start_scheduler

from admin_add_station import (
    start_add_station,
    register_admin_add_handlers,
)

from report_channel import create_report

from admin_edit_station import (
    start_edit_station,
    register_admin_edit_handlers,
)

from admin_station_status import (
    start_station_status,
    register_station_status_handlers,
)

from report_channel import send_report

from nearby_stations import (
    start_nearby,
    register_nearby_handlers,
)

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command

from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
)

from database import (
    init_db,
    add_report,
    get_time_ago,
    get_freshness,
    get_stations,
    get_station_fuel_status,
    get_connection,
)

from subscription import (
    check_subscription,
    subscription_keyboard,
)

from urllib.parse import quote


# =========================================================
# НАСТРОЙКИ
# =========================================================




TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
CHANNEL_USERNAME = "@auto_kaluga_40"

if not TOKEN:
    raise RuntimeError(
        "Не найден BOT_TOKEN в файле .env"
    )

if ADMIN_ID:
    ADMIN_ID = int(ADMIN_ID)


dp = Dispatcher()

register_admin_add_handlers(dp)
register_admin_edit_handlers(dp)
register_station_status_handlers(dp)
register_nearby_handlers(dp)


@dp.message(Command("myid"))
async def myid_handler(message: Message):
    await message.answer(
        f"🆔 Твой Telegram ID:\n\n{message.from_user.id}"
    )

# =========================================================
# КОМАНДЫ ПОЛЬЗОВАТЕЛЯ
# =========================================================

@dp.message(Command("fuel"))
async def fuel_command(message: Message):
    await show_fuel(message)


@dp.message(Command("report"))
async def report_command(message: Message):
    await show_report_menu(message)


@dp.message(Command("nearby"))
async def nearby_command(message: Message):
    await show_nearby_stations(message)


@dp.message(Command("channel"))
async def channel_command(message: Message):
    await message.answer(
        "📢 <b>Наш Telegram-канал</b>\n\n"
        "Новости, топливо и полезная информация для автомобилистов Калуги.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📢 Перейти в канал",
                        url="https://t.me/auto_kaluga_40"
                    )
                ]
            ]
        )
    )


@dp.message(Command("chat"))
async def chat_command(message: Message):
    await message.answer(
        "💬 <b>Чат автомобилистов Калуги</b>\n\n"
        "Общайтесь с другими водителями, обсуждайте дороги, "
        "АЗС и ситуацию с топливом.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💬 Открыть чат",
                        url="https://t.me/+IqwbevSSwas2MTEy"
                    )
                ]
            ]
        )
    )


@dp.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "ℹ️ <b>АвтоКалуга — помощь</b>\n\n"
        "⛽ <b>Где есть топливо</b> — актуальные отметки по АЗС.\n"
        "📝 <b>Сообщить о топливе</b> — добавить свою отметку.\n"
        "📍 <b>АЗС рядом</b> — найти ближайшие станции.\n"
        "📢 <b>Наш канал</b> — новости и отчёты.\n"
        "💬 <b>Чат</b> — общение автомобилистов.\n\n"
        "Чем больше водителей оставляют отметки, "
        "тем актуальнее информация для всех.",
        parse_mode="HTML"
    )



user_data = {}


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="⛽ Где есть топливо"),
        ],
        [
            KeyboardButton(text="📝 Сообщить о топливе"),
        ],
        [
            KeyboardButton(
                text="📍 АЗС рядом со мной",
                request_location=True,
            ),
        ],
        [
            KeyboardButton(text="📊 Отчёт по АЗС"),
        ],
        [
            KeyboardButton(text="💬 Чат автомобилистов"),
        ],
        [
            KeyboardButton(text="📢 Наш канал"),
            KeyboardButton(text="ℹ️ Помощь"),
        ],
    ],
    resize_keyboard=True,
)

@dp.message(
    
    lambda message:
    message.text == "📢 Наш Telegram-канал"
)
async def channel_button(message: Message):

    if not await require_subscription(message):
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚗 АвтоКалуга",
                    url="https://t.me/auto_kaluga_40"
                )
            ]
        ]
    )

    await message.answer(
        "Наш канал с новостями и топливом:",
        reply_markup=keyboard
    )

@dp.message(
    lambda message:
    message.text == "📊 Отчёт по АЗС"
)
async def report_button(message: Message):

    if not await require_subscription(message):
        return

    text = create_report()

    await message.answer(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

@dp.message(
    lambda message:
    message.text == "💬 Чат автомобилистов"
)
async def chat_button(message: Message):

    await chat_command(message)

@dp.message(
    lambda message:
    message.text == "📍 АЗС рядом со мной"
)
async def nearby_button(message: Message):

    await start_nearby(message)



# =========================================================
# ТОПЛИВО
# =========================================================

fuel_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="⛽ Все виды топлива"),
        ],
        [
            KeyboardButton(text="АИ-92"),
            KeyboardButton(text="АИ-95"),
        ],
        [
            KeyboardButton(text="АИ-98/100"),
            KeyboardButton(text="Дизель"),
        ],
        [
            KeyboardButton(text="✅ Готово"),
            KeyboardButton(text="⬅️ Назад"),
        ],
    ],
    resize_keyboard=True,
)


# =========================================================
# НАЛИЧИЕ
# =========================================================

availability_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🟢 Есть"),
            KeyboardButton(text="🔴 Нет"),
        ],
        [
            KeyboardButton(text="⬅️ Назад"),
        ],
    ],
    resize_keyboard=True,
)


queue_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🟢 Маленькая"),
            KeyboardButton(text="🟡 Средняя"),
            KeyboardButton(text="🔴 Большая"),
        ],
        [
            KeyboardButton(text="⏭ Пропустить"),
        ],
    ],
    resize_keyboard=True,
)


# =========================================================
# АДМИН-КЛАВИАТУРА
# =========================================================

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📊 Статистика"),
            KeyboardButton(text="⛽ Список АЗС"),
        ],
        [
            KeyboardButton(text="➕ Добавить АЗС"),
            KeyboardButton(text="✏️ Редактировать АЗС"),
        ],
        [
            KeyboardButton(text="🟢/🔴 Статус АЗС"),
        ],
        [
            KeyboardButton(text="📢 Отправить отчёт сейчас"),
        ],
        
        [
            KeyboardButton(text="🕐 Последние отметки"),
            KeyboardButton(text="👥 Пользователи"),
        ],
        [
            KeyboardButton(text="🧹 Очистить старые данные"),
        ],
        [
            KeyboardButton(text="⬅️ Выйти из админки"),
        ],
    ],
    resize_keyboard=True,
)

@dp.message(
    lambda message:
    message.text == "✏️ Редактировать АЗС"
)
async def edit_station_button(message: Message):

    if not is_admin(message.from_user.id):
        return

    await start_edit_station(message)

@dp.message(
    lambda message:
    message.text == "🟢/🔴 Статус АЗС"
)
async def station_status_button(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    await start_station_status(
        message
    )

@dp.message(
    lambda message:
    message.text == "📢 Отправить отчёт сейчас"
)
async def send_report_button(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return


    await message.answer(
        "📢 Формирую отчёт..."
    )


    bot = message.bot


    await send_report(bot)


    await message.answer(
        "✅ Отчёт отправлен в канал!"
    )

# =========================================================
# ПРОВЕРКА АДМИНА
# =========================================================

def is_admin(user_id):

    if ADMIN_ID is None:
        return False

    return user_id == ADMIN_ID


@dp.message(
    lambda message:
    message.text == "➕ Добавить АЗС"
)
async def add_station_button(message: Message):

    if not is_admin(message.from_user.id):
        return

    await start_add_station(message)


# =========================================================
# РАССТОЯНИЕ
# =========================================================

def calculate_distance(
    lat1,
    lon1,
    lat2,
    lon2,
):

    earth_radius = 6371.0

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)

    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        math.sin(delta_lat / 2) ** 2
        +
        math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return earth_radius * c


# =========================================================
# КЛАВИАТУРА АЗС
# =========================================================

def create_stations_keyboard():
    stations = get_stations()

    # Нормализуем бренд и убираем дубли
    normalized_stations = []
    seen = set()

    for station_id, display_name, brand, address in stations:
        display_name = (display_name or "").strip()
        brand = (brand or "").strip()

        # Teboil / Тебойл считаем одним брендом
        if brand.lower() in ("teboil", "тебойл"):
            brand = "Тебойл"

        # Ключ для удаления дублей
        key = (
            display_name.casefold(),
            brand.casefold(),
            (address or "").casefold()
        )

        if key in seen:
            continue

        seen.add(key)
        normalized_stations.append(
            (station_id, display_name, brand, address)
        )

    # Алфавит: сначала название АЗС, затем бренд
    normalized_stations.sort(
        key=lambda x: (
            x[1].casefold(),
            x[2].casefold()
        )
    )

    buttons = []

    for station_id, display_name, brand, address in normalized_stations:
        if brand:
            button_text = f"⛽ {display_name} — {brand}"
        else:
            button_text = f"⛽ {display_name}"

        buttons.append(
            KeyboardButton(text=button_text)
        )

    keyboard = []

    for i in range(0, len(buttons), 2):
        keyboard.append(
            buttons[i:i + 2]
        )

    keyboard.append([
        KeyboardButton(text="⬅️Назад")
    ])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )
# =========================================================
# АЗС ДЛЯ ОБРАБОТКИ
# =========================================================

def get_station_buttons():

    stations = get_stations()

    result = {}
    seen = set()

    for station_id, display_name, brand, address in stations:

        display_name = (display_name or "").strip()
        brand = (brand or "").strip()

        key = (
            display_name.casefold(),
            brand.casefold()
        )

        if key in seen:
            continue

        seen.add(key)

        if brand:
            button_text = f"⛽ {display_name} — {brand}"
        else:
            button_text = f"⛽ {display_name}"

        result[button_text] = {
            "id": station_id,
            "display_name": display_name,
            "brand": brand,
            "address": address,
        }

    return result


# =========================================================
# START
# =========================================================

@dp.callback_query(
    lambda c: c.data == "check_subscription"
)
async def check_subscription_callback(callback: CallbackQuery):

    user_id = callback.from_user.id

    # Сразу убираем "крутилку" кнопки
    await callback.answer("🔎 Проверяю подписку...")

    subscribed = await check_subscription(
        callback.bot,
        user_id
    )

    if not subscribed:

        await callback.message.edit_text(
            "⛔ <b>Вы ещё не подписаны на канал.</b>\n\n"
            "Чтобы пользоваться ботом, сначала подпишитесь "
            "на наш Telegram-канал.\n\n"
            "После подписки снова нажмите "
            "«✅ Проверить подписку».",
            reply_markup=subscription_keyboard(),
            parse_mode="HTML"
        )

        return

    # Подписка подтверждена
    user_data.pop(
        user_id,
        None
    )

    # Убираем старое сообщение с кнопками подписки
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Показываем настоящее главное меню
    await callback.message.answer(
        "🚗 <b>Добро пожаловать в АвтоКалуга!</b>\n\n"
        "Актуальная информация о наличии топлива "
        "от самих автомобилистов.\n\n"
        "Выберите действие:",
        reply_markup=main_keyboard,
        parse_mode="HTML"
    )

@dp.callback_query(
    lambda c: c.data == "check_subscription"
)
async def check_subscription_callback(callback: CallbackQuery):

    user_id = callback.from_user.id

    subscribed = await check_subscription(
        callback.bot,
        user_id
    )

    if not subscribed:

        await callback.answer(
            "❌ Вы ещё не подписаны на канал.",
            show_alert=True
        )

        await callback.message.edit_text(
            "⛔ <b>Вы ещё не подписаны на канал.</b>\n\n"
            "Чтобы пользоваться ботом, сначала подпишитесь "
            "на наш Telegram-канал.\n\n"
            "После подписки снова нажмите "
            "«✅ Проверить подписку».",
            reply_markup=subscription_keyboard(),
            parse_mode="HTML"
        )

        return

    user_data.pop(user_id, None)

    await callback.answer(
        "✅ Подписка подтверждена!"
    )

    await callback.message.edit_text(
        "🚗 <b>Добро пожаловать в АвтоКалуга!</b>\n\n"
        "Актуальная информация о наличии топлива "
        "от самих автомобилистов.\n\n"
        "Выберите действие:",
        parse_mode="HTML"
    )

    await callback.message.answer(
        "Выберите действие:",
        reply_markup=main_keyboard
    )

# =========================================================
# ADMIN
# =========================================================

@dp.message(Command("admin"))
async def admin_command(message: Message):

    user_id = message.from_user.id

    if not is_admin(user_id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    user_data[user_id] = {
        "mode": "admin"
    }

    await message.answer(
        "🛠 Админ-панель АвтоКалуга\n\n"
        "Выберите действие:",
        reply_markup=admin_keyboard,
    )


# =========================================================
# АДМИН — СТАТИСТИКА
# =========================================================

@dp.message(lambda message: message.text == "📊 Статистика")
async def admin_statistics(message: Message):

    if not is_admin(message.from_user.id):
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM stations
        WHERE active = 1
    """)

    stations_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM fuel_reports
    """)

    reports_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT user_id)
        FROM fuel_reports
    """)

    users_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM fuel_reports
        WHERE datetime(created_at)
        >= datetime('now', '-2 hours')
    """)

    fresh_reports = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM fuel_reports
        WHERE status = '🟢 Есть'
    """)

    yes_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM fuel_reports
        WHERE status = '🔴 Нет'
    """)

    no_count = cursor.fetchone()[0]

    conn.close()

    await message.answer(
        "📊 Статистика АвтоКалуги\n\n"
        f"⛽ Активных АЗС: {stations_count}\n"
        f"📝 Всего отметок: {reports_count}\n"
        f"👥 Пользователей: {users_count}\n"
        f"🕐 За последние 2 часа: {fresh_reports}\n\n"
        f"🟢 Отметок «Есть»: {yes_count}\n"
        f"🔴 Отметок «Нет»: {no_count}",
        reply_markup=admin_keyboard,
    )


# =========================================================
# АДМИН — СПИСОК АЗС
# =========================================================

@dp.message(lambda message: message.text == "⛽ Список АЗС")
async def admin_stations(message: Message):

    if not is_admin(message.from_user.id):
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            display_name,
            brand,
            address,
            latitude,
            longitude,
            active
        FROM stations
        ORDER BY city, display_name, brand
    """)

    stations = cursor.fetchall()

    conn.close()

    if not stations:

        await message.answer(
            "⛽ Список АЗС пуст.",
            reply_markup=admin_keyboard,
        )

        return

    result = [
        f"⛽ АЗС в базе: {len(stations)}\n"
    ]

    for station in stations:

        (
            station_id,
            display_name,
            brand,
            address,
            latitude,
            longitude,
            active
        ) = station

        status = (
            "🟢 активна"
            if active
            else "🔴 отключена"
        )

        coordinates = (
            "📍 координаты есть"
            if latitude is not None
            and longitude is not None
            else "⚪ координат нет"
        )

        result.append(
            f"#{station_id} "
            f"{display_name}\n"
            f"⛽ {brand or 'Без бренда'}\n"
            f"📍 {address or 'Адрес не указан'}\n"
            f"{coordinates} · {status}\n"
        )

        # Telegram ограничивает размер сообщения.
        if len("\n".join(result)) > 3500:

            await message.answer(
                "\n".join(result),
                reply_markup=admin_keyboard,
            )

            result = []

    if result:

        await message.answer(
            "\n".join(result),
            reply_markup=admin_keyboard,
        )


# =========================================================
# АДМИН — ПОСЛЕДНИЕ ОТМЕТКИ
# =========================================================

@dp.message(lambda message: message.text == "🕐 Последние отметки")
async def admin_reports(message: Message):

    if not is_admin(message.from_user.id):
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            user_id,
            station,
            fuel,
            status,
            queue,
            comment,
            created_at
        FROM fuel_reports
        ORDER BY datetime(created_at) DESC
        LIMIT 30
    """)

    reports = cursor.fetchall()

    conn.close()

    if not reports:

        await message.answer(
            "🕐 Отметок пока нет.",
            reply_markup=admin_keyboard,
        )

        return

    result = [
        "🕐 Последние 30 отметок\n"
    ]

    for (
        user_id,
        station,
        fuel,
        status,
        queue,
        comment,
        created_at
    ) in reports:

        time_ago = get_time_ago(
            created_at
        )

        result.append(
            f"{status} {fuel}\n"
            f"⛽ {station}\n"
            f"👤 ID: {user_id}\n"
            f"🚗 Очередь: {queue or 'не указана'}\n"
            f"💬 {comment or 'без комментария'}\n"
            f"🕐 {time_ago}\n"
        )

    await message.answer(
        "\n".join(result),
        reply_markup=admin_keyboard,
    )


# =========================================================
# АДМИН — ПОЛЬЗОВАТЕЛИ
# =========================================================

@dp.message(lambda message: message.text == "👥 Пользователи")
async def admin_users(message: Message):

    if not is_admin(message.from_user.id):
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            user_id,
            COUNT(*) AS reports,
            MAX(created_at) AS last_report
        FROM fuel_reports
        GROUP BY user_id
        ORDER BY reports DESC
        LIMIT 30
    """)

    users = cursor.fetchall()

    conn.close()

    if not users:

        await message.answer(
            "👥 Пользователей пока нет.",
            reply_markup=admin_keyboard,
        )

        return

    result = [
        "👥 Активные пользователи\n"
    ]

    for (
        user_id,
        reports,
        last_report
    ) in users:

        time_ago = get_time_ago(
            last_report
        )

        result.append(
            f"👤 {user_id}\n"
            f"📝 Отметок: {reports}\n"
            f"🕐 Последняя: {time_ago}\n"
        )

    await message.answer(
        "\n".join(result),
        reply_markup=admin_keyboard,
    )


# =========================================================
# АДМИН — ОЧИСТКА СТАРЫХ ДАННЫХ
# =========================================================

@dp.message(
    lambda message:
    message.text == "🧹 Очистить старые данные"
)
async def admin_cleanup(message: Message):

    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "⚠️ Сейчас будут удалены отметки "
        "старше 7 дней.\n\n"
        "Это не затронет АЗС и пользователей."
    )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM fuel_reports
        WHERE datetime(created_at)
        < datetime('now', '-7 days')
    """)

    deleted = cursor.rowcount

    conn.commit()
    conn.close()

    await message.answer(
        f"🧹 Очистка завершена.\n\n"
        f"Удалено старых отметок: {deleted}",
        reply_markup=admin_keyboard,
    )


# =========================================================
# ВЫХОД ИЗ АДМИНКИ
# =========================================================

@dp.message(
    lambda message:
    message.text == "⬅️ Выйти из админки"
)
async def exit_admin(message: Message):

    if not is_admin(message.from_user.id):
        return

    user_data.pop(
        message.from_user.id,
        None
    )

    await message.answer(
        "🚗 Главное меню:",
        reply_markup=main_keyboard,
    )


# =========================================================
# ГЕОЛОКАЦИЯ
# =========================================================

@dp.message(lambda message: message.location is not None)
async def location_handler(message: Message):

    if not await require_subscription(message):
        return

    user_lat = message.location.latitude
    user_lon = message.location.longitude

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            display_name,
            brand,
            address,
            latitude,
            longitude
        FROM stations
        WHERE active = 1
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
    """)

    stations = cursor.fetchall()
    conn.close()

    nearby = []

    for (
        station_id,
        display_name,
        brand,
        address,
        latitude,
        longitude
    ) in stations:

        distance = calculate_distance(
            user_lat,
            user_lon,
            latitude,
            longitude
        )

        nearby.append({
            "id": station_id,
            "display_name": display_name,
            "brand": brand,
            "address": address,
            "latitude": latitude,
            "longitude": longitude,
            "distance": distance,
        })

    nearby.sort(
        key=lambda station: station["distance"]
    )

    nearby = nearby[:5]

    if not nearby:

        await message.answer(
            "😔 Пока не нашёл АЗС "
            "с координатами рядом с вами.",
            reply_markup=main_keyboard
        )

        return

    text_result = "📍 <b>БЛИЖАЙШИЕ АЗС</b>\n\n"

    map_buttons = []

    for index, station in enumerate(
        nearby,
        start=1
    ):

        station_name = station["display_name"]

        if station["brand"]:
            station_title = (
                f"{station_name} — "
                f"{station['brand']}"
            )
        else:
            station_title = station_name

        distance = station["distance"]

        if distance < 1:
            distance_text = (
                f"{int(distance * 1000)} м"
            )
        else:
            distance_text = (
                f"{distance:.1f} км"
            )

        text_result += (
            f"<b>{index}. ⛽ {station_title}</b>\n"
            f"📏 {distance_text}\n"
        )

        if station["address"]:
            text_result += (
                f"📍 {station['address']}\n"
            )

        reports = get_station_fuel_status(
            station_id=station["id"],
            max_age_minutes=720
        )

        fuel_order = [
            "АИ-92",
            "АИ-95",
            "АИ-98/100",
            "Дизель",
        ]

        fuel_lines = []

        for fuel in fuel_order:

            if fuel not in reports:
                continue

            data = reports[fuel]

            yes_count = data.get("yes_count", 0)
            no_count = data.get("no_count", 0)

            # =================================================
            # ПРОТИВОРЕЧИВЫЕ ДАННЫЕ
            # =================================================

            if yes_count > 0 and no_count > 0:

                emoji = "⚠️"
                status_text = "противоречивые данные"

            # =================================================
            # ЕСТЬ
            # =================================================

            elif data["status"] == "🟢 Есть":

                emoji = "🟢"
                status_text = "есть"

            # =================================================
            # НЕТ
            # =================================================

            else:

                emoji = "🔴"
                status_text = "нет"

            time_ago = get_time_ago(
                data["created_at"]
            )

            fuel_lines.append(
                f"{emoji} {fuel} — "
                f"{status_text} ({time_ago})"
            )

        if fuel_lines:

            text_result += (
                "\n".join(fuel_lines)
                + "\n"
            )

        else:

            text_result += (
                "⚪ Нет отметок "
                "за последние 12 часов\n"
            )

        text_result += "\n"

        map_url = (
            "https://yandex.ru/maps/?"
            f"ll={station['longitude']},"
            f"{station['latitude']}"
            "&z=16"
        )

        map_buttons.append([
            InlineKeyboardButton(
                text=(
                    f"🗺 {index}. "
                    f"{station_title}"
                ),
                url=map_url
            )
        ])

    text_result += (
        "⚠️ Данные о топливе поступают "
        "от автомобилистов."
    )

    map_keyboard = InlineKeyboardMarkup(
        inline_keyboard=map_buttons
    )

    await message.answer(
        text_result,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=map_keyboard
    )

    await message.answer(
        "🚗 Главное меню:",
        reply_markup=main_keyboard
    )


# =========================================================
# ОСНОВНОЙ ОБРАБОТЧИК
# =========================================================

async def require_subscription(message: Message):

    if is_admin(message.from_user.id):
        return True

    subscribed = await check_subscription(
        message.bot,
        message.from_user.id
    )

    if not subscribed:

        await message.answer(
            "⛔ <b>Вы не подписаны на наш Telegram-канал.</b>\n\n"
            "Чтобы пользоваться ботом, подпишитесь на канал "
            "и нажмите «Проверить подписку».",
            reply_markup=subscription_keyboard(),
            parse_mode="HTML"
        )

        return False

    return True

@dp.message()
async def message_handler(message: Message):

    user_id = message.from_user.id
    text = message.text

    if text != "/start":

        if not await require_subscription(message):
            return

    # =====================================================
    # ГДЕ ЕСТЬ ТОПЛИВО
    # =====================================================

    if text == "⛽ Где есть топливо":

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                display_name,
                brand,
                address,
                latitude,
                longitude
            FROM stations
            WHERE active = 1
            ORDER BY display_name
        """)

        stations = cursor.fetchall()
        conn.close()

        result = []

        for (
            station_id,
            display_name,
            brand,
            address,
            station_lat,
            station_lon
        ) in stations:

            reports = get_station_fuel_status(
                station_id=station_id,
                max_age_minutes=720
            )

            available_fuels = []

            # =================================================
            # ВСЕ ТОПЛИВО
            #
            # «Все топливо» автоматически означает:
            # АИ-92 + АИ-95 + Дизель
            #
            # АИ-98/100 НЕ входит автоматически.
            # =================================================

            all_fuel_report = reports.get("Все виды")

            if all_fuel_report:
                all_fuel_status = all_fuel_report["status"]
                all_fuel_time = all_fuel_report["created_at"]
            else:
                all_fuel_status = None
                all_fuel_time = None

            fuel_status = {
                "АИ-92": None,
                "АИ-95": None,
                "АИ-98/100": None,
                "Дизель": None,
            }

            # =================================================
            # =================================================
            # ВСЕ ТОПЛИВО
            # =================================================
            # ВСЕ ТОПЛИВО + КОНКРЕТНЫЕ ВИДЫ
            # =================================================

            conflict_fuels = []

            all_yes_count = 0
            all_no_count = 0

            if all_fuel_report:
                all_yes_count = all_fuel_report.get("yes_count", 0)
                all_no_count = all_fuel_report.get("no_count", 0)

            all_fuel_conflict = (
                all_yes_count > 0
                and all_no_count > 0
            )

            # -------------------------------------------------
            # ОБРАБАТЫВАЕМ КАЖДЫЙ ВИД ТОПЛИВА
            # =================================================
            # ОБРАБАТЫВАЕМ КАЖДЫЙ ВИД ТОПЛИВА
            # =================================================

            for fuel in [
                "АИ-92",
                "АИ-95",
                "АИ-98/100",
                "Дизель"
            ]:

                specific = reports.get(fuel)

                # =================================================
                # АИ-98/100 — самостоятельное топливо
                # =================================================

                if fuel == "АИ-98/100":

                    if not specific:
                        continue

                    specific_time = specific.get("created_at")

                    yes_count = specific.get("yes_count", 0)
                    no_count = specific.get("no_count", 0)

                    specific_conflict = (
                        yes_count > 0
                        and no_count > 0
                    )

                    if specific_conflict:

                        conflict_fuels.append(fuel)

                    else:

                        fuel_status[fuel] = specific["status"]

                    continue

                # =================================================
                # НЕТ ALL
                # =================================================

                if not all_fuel_report:

                    if not specific:
                        continue

                    yes_count = specific.get("yes_count", 0)
                    no_count = specific.get("no_count", 0)

                    specific_conflict = (
                        yes_count > 0
                        and no_count > 0
                    )

                    if specific_conflict:

                        conflict_fuels.append(fuel)

                    else:

                        fuel_status[fuel] = specific["status"]

                    continue

                # =================================================
                # ЕСТЬ ALL
                # =================================================

                specific_time = (
                    specific.get("created_at")
                    if specific
                    else None
                )

                # =================================================
                # ALL САМ ПО СЕБЕ КОНФЛИКТУЕТ
                # =================================================

                if all_fuel_conflict:

                    # -------------------------------------------------
                    # Нет более новой конкретной отметки
                    # → конфликт ALL остаётся
                    # -------------------------------------------------

                    if (
                        not specific_time
                        or specific_time <= all_fuel_time
                    ):

                        conflict_fuels.append(fuel)

                        continue

                    # -------------------------------------------------
                    # Есть более новая конкретная отметка
                    # → она заменяет ALL
                    # -------------------------------------------------

                    yes_count = specific.get("yes_count", 0)
                    no_count = specific.get("no_count", 0)

                    specific_conflict = (
                        yes_count > 0
                        and no_count > 0
                    )

                    if specific_conflict:

                        conflict_fuels.append(fuel)

                    else:

                        fuel_status[fuel] = specific["status"]

                    continue

                # =================================================
                # ALL НЕ КОНФЛИКТУЕТ
                # =================================================

                # -------------------------------------------------
                # Нет конкретной отметки
                # → используем ALL
                # -------------------------------------------------

                if not specific:

                    if all_fuel_status == "🟢 Есть":

                        fuel_status[fuel] = "🟢 Есть"

                    elif all_fuel_status == "🔴 Нет":

                        fuel_status[fuel] = "🔴 Нет"

                    continue

                # -------------------------------------------------
                # Есть конкретная отметка
                # -------------------------------------------------

                specific_yes = specific.get("yes_count", 0)
                specific_no = specific.get("no_count", 0)

                specific_conflict = (
                    specific_yes > 0
                    and specific_no > 0
                )

                # -------------------------------------------------
                # СТАРАЯ конкретная отметка
                # -------------------------------------------------

                if (
                    specific_time
                    and all_fuel_time
                    and specific_time <= all_fuel_time
                ):

                    # ALL новее → старая конкретная
                    # отметка больше не влияет

                    if all_fuel_status == "🟢 Есть":

                        fuel_status[fuel] = "🟢 Есть"

                    elif all_fuel_status == "🔴 Нет":

                        fuel_status[fuel] = "🔴 Нет"

                    continue

                # -------------------------------------------------
                # НОВАЯ конкретная отметка
                # -------------------------------------------------

                if specific_conflict:

                    conflict_fuels.append(fuel)

                elif specific["status"] != all_fuel_status:

                    # ALL и более новая конкретная
                    # отметка противоречат друг другу

                    conflict_fuels.append(fuel)

                else:

                    # Одинаковый статус
                    fuel_status[fuel] = specific["status"]



            # =================================================
            # ФОРМИРУЕМ СПИСОК
            # =================================================

            fuel_order = [
                "АИ-92",
                "АИ-95",
                "АИ-98/100",
                "Дизель"
            ]

            available_fuels = []

            for fuel in fuel_order:

                if fuel_status[fuel] == "🟢 Есть":
                    available_fuels.append(fuel)

            # Если нет ни зелёного топлива,
            # ни конфликтов — АЗС не показываем

            if not available_fuels and not conflict_fuels:
                continue


            # =================================================
            # ФОРМИРУЕМ СПИСОК ТОПЛИВА
            # =================================================

            fuel_order = [
                "АИ-92",
                "АИ-95",
                "АИ-98/100",
                "Дизель"
            ]

            available_fuels = []

            for fuel in fuel_order:

                if fuel_status[fuel] == "🟢 Есть":
                    available_fuels.append(fuel)


            # Если нет ни подтверждённого топлива,
            # ни противоречивых данных — АЗС не показываем

            if not available_fuels and not conflict_fuels:
                continue

            # =================================================
            # НАЗВАНИЕ АЗС
            # =================================================

            station_title = display_name

            # =================================================
            # ПОСЛЕДНЯЯ ОТМЕТКА И ОЧЕРЕДЬ
            # =================================================

            latest_time = None
            latest_queue = None
            latest_comment = None

            for fuel_data in reports.values():

                item_time = fuel_data.get("created_at")

                if (
                    item_time
                    and (
                        latest_time is None
                        or item_time > latest_time
                    )
                ):
                    latest_time = item_time
                    latest_queue = fuel_data.get("queue")
                    latest_comment = fuel_data.get("comment")

            if brand:
                station_title += f" — {brand}"

            # =================================================
            # ЯНДЕКС КАРТЫ
            # =================================================

            map_query = station_title

            if address:
                map_query += f", {address}"

            map_url = (
                "https://yandex.ru/maps/?"
                f"text={quote(map_query)}"
                f"&ll={station_lon},{station_lat}"
                "&z=16"
            )

            # =================================================
            # БЛОК АЗС
            #
            # Третья строка — текстовая ссылка.
            # =================================================

            if available_fuels:
                station_text = (
                    f"🟢 <b>{station_title}</b>\n"
                    f"⛽ {', '.join(available_fuels)}\n"
                )
            else:
                station_text = (
                    f"⚠️ <b>{station_title}</b>\n"
                )

            if conflict_fuels:
                station_text += (
                    f"⚠️ {', '.join(conflict_fuels)} — "
                    f"противоречивые данные\n"
                )

            if latest_time:

                time_ago = get_time_ago(latest_time)

                station_text += (
                    f"🕐 Последняя отметка: {time_ago}\n"
                )

            if latest_queue:

                station_text += (
                    f"🚗 Очередь: {latest_queue}\n"
                )
            if latest_comment:
                station_text += (
                    f"💬 {latest_comment}\n"
                )

            station_text += (
                f'🗺 <a href="{map_url}">Открыть в Яндекс Картах</a>'
            )

            result.append(station_text)

        # =====================================================
        # НЕТ РЕЗУЛЬТАТОВ
        # =====================================================

        if not result:

            await message.answer(
                "⛽ Сейчас нет свежих подтверждений "
                "о наличии топлива.\n\n"
                "Попробуйте проверить позже.",
                reply_markup=main_keyboard
            )

            return

        # =====================================================
        # ОБЩИЙ ОТЧЁТ
        # =====================================================

        header = (
            "⛽ <b>ГДЕ ЕСТЬ ТОПЛИВО</b>\n\n"
            f"🟢 Сейчас найдено АЗС: <b>{len(result)}</b>\n\n"
        )

        footer = (
            "\n\n"
            "🕐 Учитываются отметки за последние 12 часов.\n"
            "ℹ️ Данные поступают от автомобилистов.\n\n"
            "📢 <a href=\"https://t.me/auto_kaluga_40\">Наш Telegram-канал</a>\n"
            "💬 <a href=\"https://t.me/+IqwbevSSwas2MTEy\">Чат автомобилистов</a>"
        )

        chunks = []
        current_chunk = header

        for station_text in result:

            addition = station_text + "\n\n"

            if (
                len(current_chunk)
                + len(addition)
                + len(footer)
                > 3900
            ):

                chunks.append(current_chunk)

                current_chunk = (
                    "⛽ <b>ГДЕ ЕСТЬ ТОПЛИВО</b>\n\n"
                    + addition
                )

            else:

                current_chunk += addition

        if current_chunk.strip():

            current_chunk += footer
            chunks.append(current_chunk)

        # =====================================================
        # ОТПРАВКА
        # =====================================================

        for index, chunk in enumerate(chunks):

            await message.answer(
                chunk,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=(
                    main_keyboard
                    if index == len(chunks) - 1
                    else None
                )
            )

        return

    # =====================================================
    # СООБЩИТЬ О ТОПЛИВЕ
    # =====================================================

    if text == "📝 Сообщить о топливе":

        user_data[user_id] = {
            "mode": "report"
        }

        await message.answer(
            "⛽ Выберите АЗС:",
            reply_markup=create_stations_keyboard(),
        )

        return

    if text == "📊 Отчёт по АЗС":

        if not await require_subscription(message):
            return

        await message.answer(
            create_report(),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

        return
    
    if text == "💬 Чат автомобилистов":

        await chat_command(message)

        return
    
    if text == "📢 Наш канал":

        await channel_command(message)

        return

    if text == "ℹ️ Помощь":

        await help_command(message)

        return

    # =====================================================
    # НАЗАД
    # =====================================================

    if text == "⬅️ Назад":

        user_data.pop(
            user_id,
            None
        )

        await message.answer(
            "🚗 Главное меню:",
            reply_markup=main_keyboard,
        )

        return

    # =====================================================
    # ВЫБОР АЗС
    # =====================================================

    station_buttons = get_station_buttons()

    station = station_buttons.get(text)

    if station is None:

        normalized_text = " ".join(
            text.split()
        ).strip()

        for (
            button_text,
            station_data
        ) in station_buttons.items():

            if (
                normalized_text
                == " ".join(button_text.split()).strip()
            ):

                station = station_data
                break

    if station is not None:

        print(
            "FOUND STATION:",
            station
        )

        # -------------------------------------------------
        # ПОИСК
        # -------------------------------------------------

        if (
            user_id in user_data
            and user_data[user_id].get("mode")
            == "search"
        ):

            station_name = station["display_name"]

            reports = get_station_fuel_status(
                station_id=station["id"],
                max_age_minutes=180
            )

            station_title = station_name

            if station["brand"]:

                station_title += (
                    f" — {station['brand']}"
                )

            result = [
                f"⛽ {station_title}\n"
            ]

            if station["address"]:

                result.append(
                    f"📍 {station['address']}\n"
                )

            if not reports:

                result.append(
                    "⚪ Пока нет актуальных данных "
                    "по топливу."
                )

            else:

                fuel_order = [
                    "АИ-92",
                    "АИ-95",
                    "АИ-98/100",
                    "Дизель",
                ]

                for fuel in fuel_order:

                    if fuel not in reports:
                        continue

                    data = reports[fuel]

                    status = data["status"]
                    created_at = data["created_at"]

                    yes_count = data.get(
                        "yes_count",
                        0
                    )

                    no_count = data.get(
                        "no_count",
                        0
                    )

                    total_count = data.get(
                        "total_count",
                        0
                    )

                    if status == "🟢 Есть":

                        emoji = "🟢"
                        status_text = "есть"

                    else:

                        emoji = "🔴"
                        status_text = "нет"

                    time_ago = get_time_ago(
                        created_at
                    )

                    freshness = get_freshness(
                        created_at
                    )

                    result.append(
                        f"{emoji} {fuel} — {status_text}\n"
                        f"   👥 Подтвердили: {total_count}\n"
                        f"   🟢 Есть: {yes_count} · "
                        f"🔴 Нет: {no_count}\n"
                        f"   🕐 Последняя отметка: "
                        f"{time_ago}\n"
                        f"   {freshness}\n"
                    )

                    if (
                        yes_count > 0
                        and no_count > 0
                    ):

                        result.append(
                            "   ⚠️ Есть "
                            "противоречивые данные\n"
                        )

            result.append(
                "⚠️ Данные основаны на сообщениях "
                "автомобилистов и могут измениться."
            )

            await message.answer(
                "\n".join(result),
                reply_markup=main_keyboard,
            )

            user_data.pop(
                user_id,
                None
            )

            return

        # -------------------------------------------------
        # ДОБАВЛЕНИЕ ОТМЕТКИ
        # -------------------------------------------------

        if (
            user_id in user_data
            and user_data[user_id].get("mode")
            == "report"
        ):

            user_data[user_id][
                "station_id"
            ] = station["id"]

            user_data[user_id][
                "station"
            ] = station["display_name"]

            user_data[user_id][
                "brand"
            ] = station["brand"]

            station_title = station[
                "display_name"
            ]

            if station["brand"]:

                station_title += (
                    f" — {station['brand']}"
                )

            address_text = ""

            if station["address"]:

                address_text = (
                    f"\n📍 {station['address']}"
                )

            await message.answer(
                f"⛽ {station_title}"
                f"{address_text}\n\n"
                "Какое топливо сейчас проверили?",
                reply_markup=fuel_keyboard,
            )

            return

        await message.answer(
            "Сначала выберите действие "
            "в главном меню.",
            reply_markup=main_keyboard,
        )

        return

    # =====================================================
    # КОММЕНТАРИЙ К ОТМЕТКЕ
    # =====================================================

    if (
        user_id in user_data
        and user_data[user_id].get("waiting_comment")
    ):

        station = user_data[user_id]["station"]
        station_id = user_data[user_id].get("station_id")
        fuel = user_data[user_id]["fuel"]
        status = user_data[user_id]["pending_status"]
        queue = user_data[user_id].get("queue")

        comment = None if text == "⏭ Пропустить" else text.strip()

        add_report(
            user_id=user_id,
            station=station,
            fuel=fuel,
            status=status,
            station_id=station_id,
            queue=queue,
            comment=comment,
        )

        user_data[user_id].pop("pending_status", None)
        user_data[user_id].pop("waiting_comment", None)
        user_data[user_id].pop("queue", None)
        user_data[user_id].pop("fuel", None)

        await message.answer(
            "✅ Отметка сохранена!\n\n"
            f"⛽ {station}\n"
            f"Топливо: {fuel}\n"
            f"Статус: {status}\n"
            f"Очередь: {queue or 'не указана'}\n"
            f"Комментарий: {comment or 'нет'}\n\n"
            "Можете отметить ещё один вид топлива "
            "для этой же АЗС или нажать «✅ Готово».",
            reply_markup=fuel_keyboard,
        )

        return

    # =====================================================
    # ТОПЛИВО
    # =====================================================

    fuel_types = [
        "⛽ Все виды топлива",
        "АИ-92",
        "АИ-95",
        "АИ-98/100",
        "Дизель",
    ]

    if (
        user_id in user_data
        and user_data[user_id].get("waiting_queue")
        and text in [
            "🟢 Маленькая",
            "🟡 Средняя",
            "🔴 Большая",
            "⏭ Пропустить",
        ]
    ):

        station = user_data[user_id]["station"]
        station_id = user_data[user_id].get("station_id")
        fuel = user_data[user_id]["fuel"]
        status = user_data[user_id]["pending_status"]

        queue = None if text == "⏭ Пропустить" else text

        user_data[user_id]["queue"] = queue
        user_data[user_id].pop("waiting_queue", None)
        user_data[user_id]["waiting_comment"] = True

        comment_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="⏭ Пропустить")
                ]
            ],
            resize_keyboard=True
        )

        await message.answer(
            "💬 Хотите добавить комментарий к отметке?\n\n"
            "Например: «95 есть только на 2 колонках» "
            "или «очередь только на въезд».\n\n"
            "Или нажмите «⏭ Пропустить».",
            reply_markup=comment_keyboard
        )

        return

    if text == "✅ Готово":

        if (
            user_id in user_data
            and user_data[user_id].get("mode") == "report"
            and "station" in user_data[user_id]
        ):
            station = user_data[user_id]["station"]

            await message.answer(
                f"✅ Все отметки по АЗС «{station}» сохранены.",
                reply_markup=main_keyboard,
            )

            user_data.pop(
                user_id,
                None
            )

            return

        await message.answer(
            "Сначала выберите АЗС и отметьте топливо.",
            reply_markup=main_keyboard,
        )

        return

    if text in fuel_types:

        # -------------------------------------------------
        # ВСЕ ТОПЛИВО
        # -------------------------------------------------

        if text == "⛽ Все виды топлива":

            if user_id not in user_data:

                await message.answer(
                    "Сначала выберите АЗС.",
                    reply_markup=create_stations_keyboard(),
                )

                return

            user_data[user_id]["fuel"] = "ALL"

            station = user_data[user_id][
                "station"
            ]

            await message.answer(
                f"⛽ {station}\n\n"
                "Выбран весь ассортимент топлива.\n"
                "Теперь выберите наличие:",
                reply_markup=availability_keyboard,
            )

            return

        # -------------------------------------------------
        # КОНКРЕТНОЕ ТОПЛИВО
        # -------------------------------------------------

        if (
            user_id in user_data
            and user_data[user_id].get("mode")
            == "report"
        ):

            if "station" not in user_data[user_id]:

                await message.answer(
                    "Сначала выберите АЗС.",
                    reply_markup=create_stations_keyboard(),
                )

                return

            user_data[user_id][
                "fuel"
            ] = text

            station = user_data[user_id][
                "station"
            ]

            brand = user_data[user_id].get(
                "brand"
            )

            station_title = station

            if brand:

                station_title += (
                    f" — {brand}"
                )

            await message.answer(
                f"⛽ {station_title}\n"
                f"Топливо: {text}\n\n"
                "Как сейчас с топливом?",
                reply_markup=availability_keyboard,
            )

            return

        await message.answer(
            "Сначала выберите действие "
            "в главном меню.",
            reply_markup=main_keyboard,
        )

        return

    # =====================================================
    # ЕСТЬ / НЕТ
    # =====================================================

    if text in [
    "🟢 Есть",
    "🔴 Нет"
    ]:

        if user_id not in user_data:
            await message.answer(
                "Начните с кнопки «⛽ Сообщить о топливе».",
                reply_markup=main_keyboard,
            )
            return

        if user_data[user_id].get("mode") != "report":
            await message.answer(
                "Начните с кнопки «⛽ Сообщить о топливе».",
                reply_markup=main_keyboard,
            )
            return

        if "station" not in user_data[user_id]:
            await message.answer(
                "Сначала выберите АЗС.",
                reply_markup=create_stations_keyboard(),
            )
            return

        if "fuel" not in user_data[user_id]:
            await message.answer(
                "Сначала выберите вид топлива.",
                reply_markup=fuel_keyboard,
            )
            return

        station = user_data[user_id]["station"]

        station_id = user_data[user_id].get(
            "station_id"
        )

        fuel = user_data[user_id]["fuel"]

        if fuel == "ALL":
            fuel = "Все виды"
            user_data[user_id]["fuel"] = fuel

        status = text

        user_data[user_id]["pending_status"] = status
        user_data[user_id]["waiting_queue"] = True

        await message.answer(
            "⛽ Топливо отмечено.\n\n"
            "Какая сейчас очередь на АЗС?",
            reply_markup=queue_keyboard,
        )

        return

        # Текущий fuel убираем,
        # но АЗС и режим report оставляем.
        user_data[user_id].pop(
            "fuel",
            None
        )

        return

    # =====================================================
    # КАК ЭТО РАБОТАЕТ
    # =====================================================

    if text == "ℹ️ Как это работает":

        await message.answer(
            "ℹ️ Как это работает:\n\n"
            "1️⃣ Вы заезжаете на АЗС.\n\n"
            "2️⃣ Нажимаете "
            "«📍 АЗС рядом со мной» "
            "или выбираете АЗС вручную.\n\n"
            "3️⃣ Для отметки выбираете "
            "вид топлива.\n\n"
            "4️⃣ Нажимаете 🟢 Есть "
            "или 🔴 Нет.\n\n"
            "Информация сохраняется вместе "
            "со временем отправки.\n\n"
            "Другие автомобилисты видят "
            "последние отметки и количество "
            "подтверждений."
        )

        return

    # =====================================================
    # НЕИЗВЕСТНОЕ
    # =====================================================

    await message.answer(
        "Пожалуйста, используйте кнопки меню.",
        reply_markup=main_keyboard,
    )
    
    
    # =========================================================
# ПРОВЕРКА ПОДПИСКИ
# =========================================================


# =========================================================
# ЗАПУСК
# =========================================================

# =========================================================
# КОМАНДЫ TELEGRAM
# =========================================================

async def setup_bot_commands(bot: Bot):

    # Команды для обычных пользователей
    user_commands = [
        BotCommand(
            command="start",
            description="🚗 Главное меню"
        ),
        BotCommand(
            command="fuel",
            description="⛽ Где есть топливо"
        ),
        BotCommand(
            command="report",
            description="📊 Отчёт по АЗС"
        ),
        BotCommand(
            command="nearby",
            description="📍 АЗС рядом"
        ),
        BotCommand(
            command="channel",
            description="📢 Наш канал"
        ),
        BotCommand(
            command="chat",
            description="💬 Чат автомобилистов"
        ),
        BotCommand(
            command="help",
            description="ℹ️ Помощь"
        ),
    ]

    await bot.set_my_commands(
        commands=user_commands,
        scope=BotCommandScopeDefault()
    )

    # Отдельное меню команд для администратора
    if ADMIN_ID:

        admin_commands = user_commands + [
            BotCommand(
                command="admin",
                description="🛠 Админ-панель"
            ),
            BotCommand(
                command="myid",
                description="🆔 Мой Telegram ID"
            ),
        ]

        await bot.set_my_commands(
            commands=admin_commands,
            scope=BotCommandScopeChat(
                chat_id=ADMIN_ID
            )
        )

    print("✅ Команды Telegram настроены")

async def main():

    bot = Bot(token=TOKEN)

    await setup_bot_commands(bot)

    asyncio.create_task(
        start_scheduler(bot)
    )

    print("🚗 АвтоКалуга запущен!")

    await dp.start_polling(bot)


if __name__ == "__main__":

    init_db()

    asyncio.run(main())

