from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.lang import get_locale

text = get_locale().keyboards


def tmdb_guess_keyboard(
    position: int = 0,
    total: int = 1,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if total > 1:
        rows.append(
            [
                InlineKeyboardButton(text="《", callback_data="tmdb_guess:previous"),
                InlineKeyboardButton(
                    text=f"{position + 1} / {total}",
                    callback_data="tmdb_guess:position",
                ),
                InlineKeyboardButton(text="》", callback_data="tmdb_guess:next"),
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=text.GUESS_YES,
                callback_data="tmdb_guess:yes",
            ),
            InlineKeyboardButton(text=text.GUESS_NO, callback_data="tmdb_guess:no"),
        ]
    )
    return InlineKeyboardMarkup(
        inline_keyboard=rows,
    )


def watch_status_keyboard(*, allow_completed: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if allow_completed:
        rows.append(
            [
                InlineKeyboardButton(
                    text=text.STATUS_COMPLETED,
                    callback_data="watch_status:completed",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=text.STATUS_PLANNED,
                callback_data="watch_status:planned",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tmdb_retry_keyboard(
    action: str | None = None,
    content_format: str | None = None,
) -> InlineKeyboardMarkup:
    back_callback = (
        f"back:content_type:{action}:{content_format}"
        if action and content_format
        else "back:content_type"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text.ANOTHER_TITLE,
                    callback_data="title:retry",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=text.ANOTHER_CATEGORY,
                    callback_data=back_callback,
                ),
            ],
        ],
    )
