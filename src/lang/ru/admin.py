ADMIN_ACCESS_DENIED = "Команда недоступна."
ADMIN_CALLBACK_DENIED = "Недостаточно прав"
ADMIN_OVERVIEW_FAILED = "Не удалось загрузить статистику"


def admin_overview_text(
    *,
    total_users: int,
    active_users: int,
    inactive_users: int,
    new_24h: int,
    new_7d: int,
    new_30d: int,
    active_24h: int,
    active_7d: int,
    active_30d: int,
    activated_users: int,
    activation_percent: float,
    library_items: int,
    average_library_items: float,
    rated_items: int,
    tracked_series: int,
    news_users: int,
    generated_at: str,
) -> str:
    return f"""━━━  <b>Админка · Обзор</b>  ━━━
<i>Обновлено {generated_at} UTC</i>

<b>Пользователи</b>
Всего · <b>{total_users}</b>
Активны / недоступны · {active_users} / {inactive_users}
Новые за 24 ч / 7 д / 30 д · {new_24h} / {new_7d} / {new_30d}
Активны за 24 ч / 7 д / 30 д · {active_24h} / {active_7d} / {active_30d}

<b>Активация</b>
Добавили хотя бы один тайтл · {activated_users} ({activation_percent:.1f}%)

<b>Библиотеки</b>
Всего записей · {library_items}
В среднем на пользователя · {average_library_items:.1f}
С оценкой · {rated_items}
Отслеживаются · {tracked_series}

<b>Рассылки</b>
Получают новости · {news_users}"""


__all__ = (
    "ADMIN_ACCESS_DENIED",
    "ADMIN_CALLBACK_DENIED",
    "ADMIN_OVERVIEW_FAILED",
    "admin_overview_text",
)
