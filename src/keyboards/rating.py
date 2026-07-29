from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.lang import get_locale

text = get_locale().keyboards


def rating_keyboard() -> InlineKeyboardMarkup:
    """Build a keyboard for rating one category from 1 to 10."""
    buttons = [
        InlineKeyboardButton(text=str(n), callback_data=f"rate:{n}")
        for n in range(1, 11)
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            buttons[:5],
            buttons[5:],
            [InlineKeyboardButton(text=text.BACK, callback_data="rating:back")],
        ],
    )
