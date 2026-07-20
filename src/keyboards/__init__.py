from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📚 Библиотека", callback_data="menu:library"),
                InlineKeyboardButton(text="➕ Добавить", callback_data="menu:add"),
            ],
        ],
    )


def format_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎬 Полный метр",
                    callback_data=f"format:{action}:full_length",
                ),
                InlineKeyboardButton(
                    text="📺 Сериалы",
                    callback_data=f"format:{action}:series",
                ),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back:main")],
        ],
    )


def content_type_keyboard(action: str, content_format: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎥 Фильм",
                    callback_data=f"type:{action}:{content_format}:movie",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🌸 Аниме",
                    callback_data=f"type:{action}:{content_format}:anime",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🧸 Мультфильмы",
                    callback_data=f"type:{action}:{content_format}:cartoon",
                ),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back:format:{action}")],
        ],
    )


def selected_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back:content_type")],
        ],
    )


def tmdb_guess_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="tmdb_guess:yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data="tmdb_guess:no"),
            ],
        ],
    )


def tmdb_retry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Ввести заново",
                    callback_data="title:retry",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔁 Сменить категорию",
                    callback_data="back:content_type",
                ),
            ],
        ],
    )


__all__ = (
    "content_type_keyboard",
    "format_keyboard",
    "main_menu_keyboard",
    "selected_type_keyboard",
    "tmdb_guess_keyboard",
    "tmdb_retry_keyboard",
)
