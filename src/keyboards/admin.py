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
                    text="⚙️\u00a0Система", callback_data="admin:system"
                ),
                InlineKeyboardButton(
                    text="🛠\u00a0Управление", callback_data="admin:manage"
                ),
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


def admin_system_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="↻\u00a0Обновить", callback_data="admin:system"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛠\u00a0Управление", callback_data="admin:manage"
                )
            ],
            [InlineKeyboardButton(text="‹\u00a0Обзор", callback_data="admin:overview")],
        ]
    )


def admin_management_keyboard(
    *, media_refresh: bool, notifications: bool, news: bool
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Обновить каталог (день)",
                    callback_data="admin:confirm:daily",
                ),
                InlineKeyboardButton(
                    text="Обновить метаданные",
                    callback_data="admin:confirm:weekly",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Разослать уведомления",
                    callback_data="admin:confirm:notifications",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Разослать новости", callback_data="admin:confirm:news"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Написать пользователю",
                    callback_data="admin:message:start",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Автообновление: {'вкл' if media_refresh else 'выкл'}",
                    callback_data="admin:confirm:toggle_media_refresh",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Уведомления: {'вкл' if notifications else 'выкл'}",
                    callback_data="admin:confirm:toggle_notifications",
                ),
                InlineKeyboardButton(
                    text=f"Новости: {'вкл' if news else 'выкл'}",
                    callback_data="admin:confirm:toggle_news",
                ),
            ],
            [InlineKeyboardButton(text="‹\u00a0Система", callback_data="admin:system")],
        ]
    )


def admin_confirmation_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить", callback_data=f"admin:execute:{action}"
                )
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="admin:manage")],
        ]
    )


def admin_message_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Отправить", callback_data="admin:message:send"
                )
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="admin:manage")],
        ]
    )


__all__ = (
    "admin_activity_keyboard",
    "admin_libraries_keyboard",
    "admin_notifications_keyboard",
    "admin_system_keyboard",
    "admin_management_keyboard",
    "admin_confirmation_keyboard",
    "admin_message_confirmation_keyboard",
    "admin_overview_keyboard",
    "admin_user_keyboard",
    "admin_users_keyboard",
)
