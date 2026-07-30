from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.lang import get_locale

text = get_locale().keyboards


def tracked_series_keyboard(
    page: int,
    has_more: bool,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    pagination: list[InlineKeyboardButton] = []
    if page > 0:
        pagination.append(
            InlineKeyboardButton(text="《", callback_data=f"tracked:page:{page - 1}")
        )
    if has_more:
        pagination.append(
            InlineKeyboardButton(text="》", callback_data=f"tracked:page:{page + 1}")
        )
    if pagination:
        rows.append(pagination)
    rows.append([InlineKeyboardButton(text=text.TO_MENU, callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def post_add_tracking_keyboard(
    media_id: int,
    enabled: bool,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=(text.TRACKING_DISABLE if enabled else text.TRACKING_ENABLE),
                    callback_data=f"series:tracking:add:{media_id}",
                ),
                InlineKeyboardButton(
                    text=(text.TRACKING_ACTIVE if enabled else text.TRACKING_INACTIVE),
                    callback_data="series:tracking:status",
                ),
            ],
            [InlineKeyboardButton(text=text.TO_MENU, callback_data="back:main")],
        ]
    )


def notification_keyboard(
    batch_id: int,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup | None:
    if total_pages <= 1:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="《",
                    callback_data=(
                        f"series:notifications:{batch_id}:{page - 1}"
                        if page > 0
                        else "series:notifications:noop"
                    ),
                ),
                InlineKeyboardButton(
                    text=f"{page + 1}/{total_pages}",
                    callback_data="series:notifications:noop",
                ),
                InlineKeyboardButton(
                    text="》",
                    callback_data=(
                        f"series:notifications:{batch_id}:{page + 1}"
                        if page < total_pages - 1
                        else "series:notifications:noop"
                    ),
                ),
            ]
        ]
    )


__all__ = (
    "notification_keyboard",
    "post_add_tracking_keyboard",
    "tracked_series_keyboard",
)
