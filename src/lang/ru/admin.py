import html

ADMIN_ACCESS_DENIED = "Команда недоступна."
ADMIN_CALLBACK_DENIED = "Недостаточно прав"
ADMIN_OVERVIEW_FAILED = "Не удалось загрузить статистику"
ADMIN_USERS_FAILED = "Не удалось загрузить пользователей"
ADMIN_USER_NOT_FOUND = "Пользователь не найден"
ADMIN_INVALID_CALLBACK = "Некорректная команда"
ADMIN_ACTIVITY_FAILED = "Не удалось загрузить активность"


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


def admin_users_text(*, total_users: int, page: int, total_pages: int) -> str:
    return f"""━━━  <b>Админка · Пользователи</b>  ━━━
Всего · <b>{total_users}</b>
Страница · {page} из {total_pages}

<i>Выберите пользователя</i>"""


def admin_user_text(
    *,
    user_id: int,
    username: str | None,
    display_name: str | None,
    is_active: int,
    news_enabled: int,
    started_at: str,
    last_started_at: str,
    last_activity_at: str,
    library_items: int,
    planned_items: int,
    watching_items: int,
    completed_items: int,
    on_hold_items: int,
    dropped_items: int,
    rated_items: int,
    average_rating: float | None,
    tracked_series: int,
) -> str:
    name = html.escape(display_name or "Имя пока неизвестно")
    username_text = f"@{html.escape(username)}" if username else "username отсутствует"
    status = "активен" if is_active else "бот недоступен"
    news = "включены" if news_enabled else "выключены"
    rating = "—" if average_rating is None else f"{average_rating:.1f}"
    return f"""━━━  <b>Админка · Пользователь</b>  ━━━
<b>{name}</b>
{username_text} · <code>{user_id}</code>

<b>Состояние</b>
Доступ · {status}
Новости · {news}
Первый запуск · {started_at} UTC
Последний /start · {last_started_at} UTC
Последняя активность · {last_activity_at} UTC

<b>Библиотека</b>
Всего · {library_items}
Хочу посмотреть · {planned_items}
Смотрю · {watching_items}
Просмотрено · {completed_items}
Отложено · {on_hold_items}
Брошено · {dropped_items}
С оценкой · {rated_items} · средняя {rating}
Отслеживаются · {tracked_series}"""


def admin_activity_text(
    *,
    days: int,
    dau: int,
    wau: int,
    mau: int,
    new_users: int,
    returning_users: int,
    searches: int,
    library_opens: int,
    media_added: int,
    ratings_set: int,
    progress_updates: int,
    daily: tuple[tuple[str, int, int, int], ...],
    generated_at: str,
) -> str:
    daily_lines = "\n".join(
        f"{event_date[8:10]}.{event_date[5:7]} · {active} / +{new} / ↩{returning}"
        for event_date, active, new, returning in daily
    )
    return f"""━━━  <b>Админка · Активность</b>  ━━━
<i>Обновлено {generated_at} UTC</i>

<b>Аудитория</b>
DAU / WAU / MAU · <b>{dau} / {wau} / {mau}</b>

<b>За {days} дней</b>
Новые пользователи · {new_users}
Вернувшиеся пользователи · {returning_users}
Поиски · {searches}
Открытия библиотеки · {library_opens}
Добавления тайтлов · {media_added}
Оценки · {ratings_set}
Обновления прогресса · {progress_updates}

<b>Динамика</b>
<i>Активные / новые / вернувшиеся</i>
<code>{daily_lines}</code>"""


__all__ = (
    "ADMIN_ACCESS_DENIED",
    "ADMIN_ACTIVITY_FAILED",
    "ADMIN_CALLBACK_DENIED",
    "ADMIN_OVERVIEW_FAILED",
    "ADMIN_INVALID_CALLBACK",
    "ADMIN_USERS_FAILED",
    "ADMIN_USER_NOT_FOUND",
    "admin_overview_text",
    "admin_activity_text",
    "admin_user_text",
    "admin_users_text",
)
