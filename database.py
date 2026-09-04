import sqlite3

from datetime import datetime, timezone, timedelta

MSK = timezone(timedelta(hours=3))


DB_NAME = "avto_kaluga.db"


# =========================================================
# ПОДКЛЮЧЕНИЕ
# =========================================================

def get_connection():
    return sqlite3.connect(DB_NAME)


# =========================================================
# ИНИЦИАЛИЗАЦИЯ
# =========================================================

def init_db():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            brand TEXT,
            address TEXT,
            city TEXT DEFAULT 'Калуга',
            latitude REAL,
            longitude REAL,
            active INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fuel_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            station_id INTEGER,
            station TEXT,
            fuel TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Проверяем старую базу
    cursor.execute("PRAGMA table_info(fuel_reports)")

    columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    if "station_id" not in columns:

        cursor.execute("""
            ALTER TABLE fuel_reports
            ADD COLUMN station_id INTEGER
        """)

    if "station" not in columns:

        cursor.execute("""
            ALTER TABLE fuel_reports
            ADD COLUMN station TEXT
        """)

    if "queue" not in columns:

        cursor.execute("""
            ALTER TABLE fuel_reports
            ADD COLUMN queue TEXT
        """)

    if "comment" not in columns:
        cursor.execute("""
            ALTER TABLE fuel_reports
            ADD COLUMN comment TEXT
        """)

    conn.commit()
    conn.close()


# =========================================================
# ДОБАВЛЕНИЕ АЗС
# =========================================================

def add_station(
    display_name,
    brand=None,
    address=None,
    city="Калуга",
    latitude=None,
    longitude=None
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO stations
        (
            display_name,
            brand,
            address,
            city,
            latitude,
            longitude
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        display_name,
        brand,
        address,
        city,
        latitude,
        longitude
    ))

    conn.commit()

    station_id = cursor.lastrowid

    conn.close()

    return station_id


# =========================================================
# СПИСОК АЗС
# =========================================================

def get_stations():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            display_name,
            brand,
            address
        FROM stations
        WHERE active = 1
        ORDER BY display_name, brand
    """)

    stations = cursor.fetchall()

    conn.close()

    unique = []
    seen = set()

    for station in stations:

        name = (station[1] or "").strip().lower()
        brand = (station[2] or "").strip().lower()
        address = (station[3] or "").strip().lower()

        key = (
            name,
            brand,
            address,
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(station)

    return unique

    return stations


# =========================================================
# ДОБАВЛЕНИЕ / ОБНОВЛЕНИЕ ОТМЕТКИ
# =========================================================

def add_report(
    user_id,
    station,
    status,
    station_id=None,
    fuel = "",
    queue=None,
    comment=None
):

    print(
        "DEBUG ADD_REPORT:",
        user_id,
        station,
        status,
        station_id,
        fuel,
        queue,
        flush=True
    )
    conn = get_connection()
    cursor = conn.cursor()

    # Если ID АЗС не передан — ищем по названию
    if station_id is None:

        clean_station = station.replace(
            "⛽ ",
            ""
        ).strip()

        # Ищем предыдущую отметку этого пользователя
        # по этой АЗС и этому виду топлива
        cursor.execute("""
            SELECT id
            FROM fuel_reports
            WHERE datetime(created_at) >= datetime('now','-12 hours')
            AND user_id = ?
            AND fuel = ?
            AND (
                station_id = ?
                OR (
                    station_id IS NULL
                    AND station = ?
                )
            )
            ORDER BY datetime(created_at) DESC
            LIMIT 1
        """, (
            user_id,
            fuel,
            station_id,
            station
        ))

        station_row = cursor.fetchone()

        if station_row:
            station_id = station_row[0]

    created_at = datetime.now(MSK).isoformat(
        timespec="seconds"
    )

    # Ищем предыдущую отметку этого пользователя
    # по этой АЗС и этому виду топлива
    cursor.execute("""
        SELECT id
        FROM fuel_reports
        WHERE user_id = ?
        AND station_id = ?
        AND fuel = ?
        ORDER BY datetime(created_at) DESC
        LIMIT 1
    """, (
        user_id,
        station_id,
        fuel
    ))

    existing = cursor.fetchone()

    if existing:

        report_id = existing[0]

        cursor.execute("""
            UPDATE fuel_reports
            SET
                station = ?,
                status = ?,
                created_at = ?,
                queue = ?,
                comment = ?
            WHERE id = ?
        """, (
            station,
            status,
            created_at,
            queue,
            comment,
            report_id,
        ))

    else:
                # удаляем старую отметку этого пользователя
        cursor.execute(
            """
            DELETE FROM fuel_reports
            WHERE user_id = ?
            AND station = ?
            AND fuel = ?
            """,
            (
                user_id,
                station,
                fuel,
            )
        )
        
        cursor.execute("""
            INSERT INTO fuel_reports
            (
                user_id,
                station_id,
                station,
                fuel,
                status,
                created_at,
                queue,
                comment
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            station_id,
            station,
            fuel,
            status,
            created_at,
            queue,
            comment
        ))

    conn.commit()
    conn.close()


# =========================================================
# ПОСЛЕДНИЕ ОТМЕТКИ ПО ТОПЛИВУ
# =========================================================

def get_latest_by_fuel(
    fuel,
    max_age_minutes=120
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            station,
            status,
            created_at
        FROM fuel_reports
        WHERE fuel = ?
        AND datetime(created_at)
            >= datetime('now', ?)
        ORDER BY datetime(created_at) DESC
    """, (
        fuel,
        f"-{max_age_minutes} minutes"
    ))

    rows = cursor.fetchall()

    conn.close()

    latest = {}

    for station, status, created_at in rows:

        if station not in latest:

            latest[station] = {
                "status": status,
                "created_at": created_at
            }

    return latest


# =========================================================
# КАРТОЧКА АЗС
# =========================================================

def get_station_fuel_status(
    station_name=None,
    station_id=None,
    max_age_minutes=1440
):

    conn = get_connection()
    cursor = conn.cursor()
    if station_id is not None:
        station_filter = "station_id = ?"
        station_value = station_id
    else:
        station_filter = "station = ?"
        station_value = station_name
    cursor.execute(f"""
        SELECT
            user_id,
            fuel,
            status,
            created_at,
            queue,
            comment
        FROM fuel_reports
        WHERE {station_filter}
          AND datetime(created_at)
              >= datetime('now', ?)
        ORDER BY datetime(created_at) DESC
    """, (
        station_value,
        f"-{max_age_minutes} minutes"
    ))

    rows = cursor.fetchall()

    conn.close()

    latest = {}

    for user_id, fuel, status, created_at, queue, comment in rows:

        if fuel == "ALL":
            fuel = "Все виды"
            
        if fuel not in latest:

            latest[fuel] = {
                "users": {}
            }

        # Важный момент:
        # запрос идёт от НОВЫХ отметок к СТАРЫМ.
        # Поэтому первого пользователя уже записали
        # как его последнюю отметку.
        #
        # Старую отметку этого же пользователя
        # больше не трогаем.

        if user_id not in latest[fuel]["users"]:

            latest[fuel]["users"][user_id] = {
                "status": status,
                "created_at": created_at,
                "queue": queue,
                "comment": comment,
            }

    # =====================================================
    # СЧИТАЕМ РЕЗУЛЬТАТ
    # =====================================================

    result = {}

    for fuel, data in latest.items():

        users = data["users"]

        yes_count = 0
        no_count = 0

        latest_status = None
        latest_time = None

        for user_data in users.values():

            status = user_data["status"]
            created_at = user_data["created_at"]

            if status == "🟢 Есть":
                yes_count += 1

            elif status == "🔴 Нет":
                no_count += 1

            if (
                latest_time is None
                or created_at > latest_time
            ):
                latest_time = created_at
                latest_status = status

        result[fuel] = {
            "status": latest_status,
            "created_at": latest_time,
            "yes_count": yes_count,
            "no_count": no_count,
            "total_count": len(users),
            "queue": next(
                (
                    user_data["queue"]
                    for user_data in users.values()
                    if user_data["created_at"] == latest_time
                ),
                None
            ),
            "comment": next(
                (
                    user_data["comment"]
                    for user_data in users.values()
                    if user_data["created_at"] == latest_time
                ),
                None
            ),
        }

    return result

# =========================================================
# ВРЕМЯ
# =========================================================

def get_time_ago(created_at):

    created = datetime.fromisoformat(created_at)

    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    now = datetime.now(MSK)

    seconds = int(
        (now - created).total_seconds()
    )

    if seconds < 60:
        return "только что"

    minutes = seconds // 60

    if minutes == 1:
        return "1 минуту назад"

    if minutes < 5:
        return f"{minutes} минуты назад"

    if minutes < 60:
        return f"{minutes} минут назад"

    hours = minutes // 60

    if hours == 1:
        return "1 час назад"

    return f"{hours} ч. назад"


# =========================================================
# СВЕЖЕСТЬ
# =========================================================

def get_freshness(created_at):

    created = datetime.fromisoformat(
        created_at
    )

    now = datetime.now(MSK)

    minutes = int(
        (now - created).total_seconds() / 60
    )

    if minutes <= 30:
        return "🟢 Свежая информация"

    if minutes <= 120:
        return "🟡 Информация устаревает"

    return "⚪ Информация устарела"

def calculate_reliability(
    yes_count,
    no_count
):

    total = yes_count + no_count

    if total == 0:
        return 0

    return int(
        yes_count / total * 100
    )


def get_station_reliability(
    station_name
):

    data = get_station_fuel_status(
        station_name
    )

    result = {}

    for fuel, item in data.items():

        percent = calculate_reliability(
            item["yes_count"],
            item["no_count"]
        )

        result[fuel] = {
            **item,
            "reliability": percent
        }

        

    return result
