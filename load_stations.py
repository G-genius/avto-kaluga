from database import get_connection
from stations_data import STATIONS


def load_stations():

    conn = get_connection()
    cursor = conn.cursor()

    added = 0
    updated = 0

    for station in STATIONS:

        cursor.execute("""
            SELECT id
            FROM stations
            WHERE display_name = ?
            AND brand = ?
            AND address = ?
            LIMIT 1
        """, (
            station["display_name"],
            station["brand"],
            station["address"],
        ))

        existing = cursor.fetchone()

        if existing:

            cursor.execute("""
                UPDATE stations
                SET
                    city = ?,
                    latitude = ?,
                    longitude = ?,
                    active = 1
                WHERE id = ?
            """, (
                station["city"],
                station["latitude"],
                station["longitude"],
                existing[0],
            ))

            updated += 1

        else:

            cursor.execute("""
                INSERT INTO stations
                (
                    display_name,
                    brand,
                    address,
                    city,
                    latitude,
                    longitude,
                    active
                )
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (
                station["display_name"],
                station["brand"],
                station["address"],
                station["city"],
                station["latitude"],
                station["longitude"],
            ))

            added += 1

    conn.commit()
    conn.close()

    print("================================")
    print("АЗС загружены")
    print(f"Добавлено: {added}")
    print(f"Обновлено: {updated}")
    print(f"Всего в файле: {len(STATIONS)}")
    print("================================")


if __name__ == "__main__":
    load_stations()