from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.lang import get_locale

text = get_locale().keyboards
rating_text = get_locale().rating


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


def badge_keyboard(prefix: str) -> InlineKeyboardMarkup:
    if prefix not in {"rating_badge", "library_badge"}:
        raise ValueError("Unknown badge callback prefix")
    options = [
        InlineKeyboardButton(
            text=f"{emoji} {label}",
            callback_data=f"{prefix}:{code}",
        )
        for code, emoji, label in rating_text.BADGE_OPTIONS
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            options[:2],
            options[2:],
            [
                InlineKeyboardButton(
                    text="Без лычки",
                    callback_data=f"{prefix}:none",
                )
            ],
            [
                InlineKeyboardButton(
                    text=text.BACK,
                    callback_data=f"{prefix}:back",
                )
            ],
        ]
    )
