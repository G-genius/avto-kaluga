def calculate_reliability(
    yes_count,
    no_count
):

    total = yes_count + no_count

    if total == 0:
        return 0

    return round(
        yes_count / total * 100
    )


def reliability_text(percent):

    if percent >= 90:
        return "⭐ Отлично"

    if percent >= 70:
        return "👍 Хорошо"

    if percent >= 50:
        return "⚠️ Спорно"

    return "❌ Мало данных"