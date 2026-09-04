from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


CHANNEL_ID = -1004439494485
CHANNEL_LINK = "https://t.me/auto_kaluga_40"


def subscription_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Подписаться на канал",
                    url=CHANNEL_LINK
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Проверить подписку",
                    callback_data="check_subscription"
                )
            ]
        ]
    )


async def check_subscription(bot, user_id):

    try:
        member = await bot.get_chat_member(
            chat_id=CHANNEL_ID,
            user_id=user_id
        )

        return member.status in [
            "member",
            "administrator",
            "creator"
        ]

    except Exception as e:
        print("Ошибка проверки подписки:", e)
        return False
