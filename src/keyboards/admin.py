from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_overview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="↻\u00a0Обновить",
                    callback_data="admin:overview",
                )
            ]
        ]
    )


__all__ = ("admin_overview_keyboard",)
