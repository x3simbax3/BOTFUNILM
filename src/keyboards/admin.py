from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊\u00a0Статистика",
                    callback_data="admin:stats",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✉️\u00a0Своя рассылка",
                    callback_data="admin:broadcast",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📰\u00a0Новость из API",
                    callback_data="admin:confirm:news",
                )
            ],
        ]
    )


def admin_statistics_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📥\u00a0Выгрузить Excel",
                    callback_data="admin:export:users",
                )
            ],
            [
                InlineKeyboardButton(
                    text="↻\u00a0Обновить",
                    callback_data="admin:stats",
                )
            ],
            [InlineKeyboardButton(text="‹\u00a0Назад", callback_data="admin:menu")],
        ]
    )


def admin_broadcast_format_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Только текст",
                    callback_data="admin:broadcast:text",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Фото и подпись",
                    callback_data="admin:broadcast:photo",
                )
            ],
            [InlineKeyboardButton(text="‹\u00a0Назад", callback_data="admin:menu")],
        ]
    )


def admin_broadcast_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Отправить всем",
                    callback_data="admin:broadcast:send",
                )
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="admin:menu")],
        ]
    )


def admin_confirmation_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить",
                    callback_data=f"admin:execute:{action}",
                )
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="admin:menu")],
        ]
    )


__all__ = (
    "admin_broadcast_confirmation_keyboard",
    "admin_broadcast_format_keyboard",
    "admin_confirmation_keyboard",
    "admin_menu_keyboard",
    "admin_statistics_keyboard",
)
