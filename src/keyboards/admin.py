from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_overview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥\u00a0Пользователи",
                    callback_data="admin:users:1",
                )
            ],
            [
                InlineKeyboardButton(
                    text="▥\u00a0Активность",
                    callback_data="admin:activity:7",
                )
            ],
            [
                InlineKeyboardButton(
                    text="▤\u00a0Библиотеки",
                    callback_data="admin:libraries",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔔\u00a0Уведомления",
                    callback_data="admin:notifications",
                )
            ],
            [
                InlineKeyboardButton(
                    text="↻\u00a0Обновить",
                    callback_data="admin:overview",
                )
            ],
        ]
    )


def admin_users_keyboard(
    users: list[tuple[int, str]],
    *,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"admin:user:{user_id}:{page}")]
        for user_id, label in users
    ]
    navigation = []
    if page > 1:
        navigation.append(
            InlineKeyboardButton(
                text="‹\u00a0Пред.",
                callback_data=f"admin:users:{page - 1}",
            )
        )
    navigation.append(
        InlineKeyboardButton(
            text=f"{page}/{total_pages}",
            callback_data=f"admin:users:{page}",
        )
    )
    if page < total_pages:
        navigation.append(
            InlineKeyboardButton(
                text="След.\u00a0›",
                callback_data=f"admin:users:{page + 1}",
            )
        )
    rows.append(navigation)
    rows.append(
        [InlineKeyboardButton(text="‹\u00a0Обзор", callback_data="admin:overview")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_user_keyboard(page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="‹\u00a0К пользователям",
                    callback_data=f"admin:users:{page}",
                )
            ],
            [InlineKeyboardButton(text="⌂\u00a0Обзор", callback_data="admin:overview")],
        ]
    )


def admin_activity_keyboard(days: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=("✓\u00a07 дней" if days == 7 else "7 дней"),
                    callback_data="admin:activity:7",
                ),
                InlineKeyboardButton(
                    text=("✓\u00a030 дней" if days == 30 else "30 дней"),
                    callback_data="admin:activity:30",
                ),
            ],
            [InlineKeyboardButton(text="‹\u00a0Обзор", callback_data="admin:overview")],
        ]
    )


def admin_libraries_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="↻\u00a0Обновить",
                    callback_data="admin:libraries",
                )
            ],
            [InlineKeyboardButton(text="‹\u00a0Обзор", callback_data="admin:overview")],
        ]
    )


def admin_notifications_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="↻\u00a0Обновить",
                    callback_data="admin:notifications",
                )
            ],
            [InlineKeyboardButton(text="‹\u00a0Обзор", callback_data="admin:overview")],
        ]
    )


__all__ = (
    "admin_activity_keyboard",
    "admin_libraries_keyboard",
    "admin_notifications_keyboard",
    "admin_overview_keyboard",
    "admin_user_keyboard",
    "admin_users_keyboard",
)
