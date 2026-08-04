import html

ADMIN_ACCESS_DENIED = "Команда недоступна."
ADMIN_CALLBACK_DENIED = "Недостаточно прав"
ADMIN_OVERVIEW_FAILED = "Не удалось загрузить статистику"
ADMIN_USERS_FAILED = "Не удалось загрузить пользователей"
ADMIN_USER_NOT_FOUND = "Пользователь не найден"
ADMIN_INVALID_CALLBACK = "Некорректная команда"
ADMIN_ACTIVITY_FAILED = "Не удалось загрузить активность"
ADMIN_LIBRARIES_FAILED = "Не удалось загрузить статистику библиотек"
ADMIN_NOTIFICATIONS_FAILED = "Не удалось загрузить статистику уведомлений"
ADMIN_SYSTEM_FAILED = "Не удалось загрузить состояние системы"
ADMIN_ACTION_FAILED = "Не удалось выполнить действие"


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


def admin_libraries_text(
    *,
    total_items: int,
    users_with_library: int,
    average_items_per_user: float,
    planned_items: int,
    watching_items: int,
    completed_items: int,
    on_hold_items: int,
    full_length_items: int,
    series_items: int,
    movie_items: int,
    anime_items: int,
    cartoon_items: int,
    rated_items: int,
    average_rating: float | None,
    tracked_series: int,
    popular_movies: tuple[tuple[str, int], ...],
    popular_series: tuple[tuple[str, int], ...],
    generated_at: str,
) -> str:
    rating = "—" if average_rating is None else f"{average_rating:.1f}"

    def popular_text(items: tuple[tuple[str, int], ...]) -> str:
        if not items:
            return "—"
        return "\n".join(
            f"{index}. {html.escape(title)} · {users}"
            for index, (title, users) in enumerate(items, start=1)
        )

    return f"""━━━  <b>Админка · Библиотеки</b>  ━━━
<i>Обновлено {generated_at} UTC</i>

<b>Объём</b>
Всего записей · <b>{total_items}</b>
Пользователей с библиотекой · {users_with_library}
В среднем на такого пользователя · {average_items_per_user:.1f}

<b>Статусы</b>
Хочу посмотреть · {planned_items}
Смотрю · {watching_items}
Просмотрено · {completed_items}
Отложено · {on_hold_items}

<b>Форматы и категории</b>
Полный метр / сериалы · {full_length_items} / {series_items}
Кино / аниме / мультфильмы · {movie_items} / {anime_items} / {cartoon_items}

<b>Оценки и отслеживание</b>
С оценкой · {rated_items} · средняя {rating}
Активные отслеживания · {tracked_series}

<b>Популярный полный метр</b>
{popular_text(popular_movies)}

<b>Популярные сериалы</b>
{popular_text(popular_series)}"""


def admin_notifications_text(
    *,
    news_subscribers: int,
    news_opted_out: int,
    series_subscribers: int,
    series_subscriptions: int,
    pending_series_notifications: int,
    sent_series_notifications: int,
    pending_release_notifications: int,
    sent_release_notifications: int,
    news_sent_30d: int,
    release_messages_sent_30d: int,
    selected_30d: int,
    sent_30d: int,
    failed_30d: int,
    deactivated_30d: int,
    success_percent_30d: float,
    blocked_users: int,
    last_delivery_at: str | None,
    generated_at: str,
) -> str:
    last_delivery = f"{last_delivery_at} UTC" if last_delivery_at else "ещё не было"
    return f"""━━━  <b>Админка · Уведомления</b>  ━━━
<i>Обновлено {generated_at} UTC</i>

<b>Подписки</b>
Получают новости · {news_subscribers}
Отключили новости · {news_opted_out}
Подписчики сериалов · {series_subscribers}
Активные подписки на сериалы · {series_subscriptions}

<b>Очереди и история</b>
Новые серии: ожидают / отправлены · {pending_series_notifications} / {sent_series_notifications}
Выход тайтлов: ожидают / отправлены · {pending_release_notifications} / {sent_release_notifications}

<b>Доставка за 30 дней</b>
Выбрано получателей · {selected_30d}
Доставлено · {sent_30d} ({success_percent_30d:.1f}%)
Новости доставлены · {news_sent_30d}
Сообщения о релизах · {release_messages_sent_30d}
Ошибки Telegram · {failed_30d}
Блокировки при отправке · {deactivated_30d}

<b>Доступность</b>
Заблокировали бота · {blocked_users}
Последняя рассылка · {last_delivery}"""


def admin_system_text(
    *,
    catalog_items: int,
    tmdb_errors: int,
    daily_overdue: int,
    weekly_overdue: int,
    pending_series_notifications: int,
    pending_release_notifications: int,
    database_size_bytes: int,
    database_free_bytes: int,
    database_journal_mode: str,
    redis_available: bool,
    queued_jobs: int,
    worker_state: str | None,
    worker_job: str | None,
    worker_updated_at: str | None,
    generated_at: str,
) -> str:
    redis = "доступен" if redis_available else "недоступен"
    worker = {
        "idle": "ожидает",
        "running": "выполняет задачу",
        "failed": "ошибка последней задачи",
    }.get(worker_state, "нет heartbeat")
    worker_details = f" · {html.escape(worker_job)}" if worker_job else ""
    heartbeat = worker_updated_at or "—"
    size_mb = database_size_bytes / 1024**2
    free_mb = database_free_bytes / 1024**2
    return f"""━━━  <b>Админка · Система</b>  ━━━
<i>Обновлено {generated_at} UTC</i>

<b>Каталог и TMDB</b>
Тайтлов · <b>{catalog_items}</b>
Ошибок последнего обновления · {tmdb_errors}
Просрочены: ежедневные / недельные · {daily_overdue} / {weekly_overdue}

<b>Очереди уведомлений</b>
Новые серии / релизы · {pending_series_notifications} / {pending_release_notifications}
Ручные задачи · {queued_jobs}

<b>Инфраструктура</b>
Media worker · {worker}{worker_details}
Heartbeat · {heartbeat}
Redis · {redis}
SQLite · доступна · {size_mb:.1f} МБ, свободно {free_mb:.1f} МБ
Журнал SQLite · {html.escape(database_journal_mode)}"""


def admin_management_text(
    *, media_refresh: bool, notifications: bool, news: bool
) -> str:
    def status(enabled: bool) -> str:
        return "включено" if enabled else "выключено"

    return f"""━━━  <b>Админка · Управление</b>  ━━━

Ручные задачи ставятся в очередь media worker.

<b>Автоматические функции</b>
Обновление каталога · {status(media_refresh)}
Уведомления о релизах · {status(notifications)}
Новости · {status(news)}

<i>Каждое изменение потребует отдельного подтверждения.</i>"""


__all__ = (
    "ADMIN_ACCESS_DENIED",
    "ADMIN_ACTIVITY_FAILED",
    "ADMIN_CALLBACK_DENIED",
    "ADMIN_OVERVIEW_FAILED",
    "ADMIN_INVALID_CALLBACK",
    "ADMIN_LIBRARIES_FAILED",
    "ADMIN_NOTIFICATIONS_FAILED",
    "ADMIN_SYSTEM_FAILED",
    "ADMIN_ACTION_FAILED",
    "ADMIN_USERS_FAILED",
    "ADMIN_USER_NOT_FOUND",
    "admin_overview_text",
    "admin_activity_text",
    "admin_libraries_text",
    "admin_notifications_text",
    "admin_system_text",
    "admin_management_text",
    "admin_user_text",
    "admin_users_text",
)
