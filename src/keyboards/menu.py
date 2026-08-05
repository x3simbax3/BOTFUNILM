from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.lang import get_locale

text = get_locale().keyboards


def main_menu_keyboard(news_enabled: bool = True) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text.MAIN_LIBRARY, callback_data="menu:library"
                ),
                InlineKeyboardButton(
                    text=text.MAIN_SETTINGS, callback_data="menu:settings"
                ),
            ],
        ],
    )


def library_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text.LIBRARY_ALL, callback_data="menu:library:all"
                )
            ],
            [
                InlineKeyboardButton(
                    text=text.MAIN_TRACKED, callback_data="menu:tracked"
                )
            ],
            [
                InlineKeyboardButton(
                    text=text.MAIN_ADD, callback_data="menu:add"
                )
            ],
            [InlineKeyboardButton(text=text.TO_MENU, callback_data="back:main")],
        ],
    )


def settings_keyboard(news_enabled: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=(text.MAIN_NEWS_ON if news_enabled else text.MAIN_NEWS_OFF),
                    callback_data="menu:news",
                )
            ],
            [InlineKeyboardButton(text=text.TO_MENU, callback_data="back:main")],
        ]
    )


def format_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text.FORMAT_FULL_LENGTH,
                    callback_data=f"format:{action}:full_length",
                ),
                InlineKeyboardButton(
                    text=text.FORMAT_SERIES,
                    callback_data=f"format:{action}:series",
                ),
            ],
            [InlineKeyboardButton(text=text.BACK, callback_data="back:library_menu")],
        ],
    )


def content_type_keyboard(action: str, content_format: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text.TYPE_MOVIE,
                    callback_data=f"type:{action}:{content_format}:movie",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=text.TYPE_ANIME,
                    callback_data=f"type:{action}:{content_format}:anime",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=text.TYPE_CARTOON,
                    callback_data=f"type:{action}:{content_format}:cartoon",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=text.BACK,
                    callback_data=f"back:format:{action}",
                )
            ],
        ],
    )


def selected_type_keyboard(action: str, content_format: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text.BACK,
                    callback_data=f"back:content_type:{action}:{content_format}",
                ),
            ],
        ],
    )
