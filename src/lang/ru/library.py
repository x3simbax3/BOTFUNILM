from datetime import date
from html import escape

from .common import DESCRIPTION_NOT_FOUND
from .menu import CONTENT_TYPE_TITLES, MEDIA_KIND_TITLES

USER_STATUS_TITLES = {
    "planned": "Хочу посмотреть",
    "watching": "Смотрю",
    "completed": "Просмотрено",
    "on_hold": "Отложено",
    "dropped": "Брошено",
}
USER_STATUS_ICONS = {
    "planned": "○",
    "watching": "◉",
    "completed": "✓",
    "on_hold": "Ⅱ",
    "dropped": "×",
}
ACTIVE_TMDB_SERIES_STATUSES = frozenset(
    {"Returning Series", "Planned", "In Production"}
)
LIBRARY_ITEM_DIVIDER = "┈┈┈┈┈┈┈┈┈┈┈┈┈"
LIBRARY_HEADING = "╭ <b>Моя библиотека</b>"

UNKNOWN_FILTER = "Неизвестный фильтр"
FILTER_SAVE_FAILED = "Не удалось сохранить фильтр"
INVALID_PAGE = "Некорректная страница"
LIBRARY_OPEN_FAILED = "Не удалось открыть библиотеку"
ITEM_OPEN_FAILED = "Не удалось открыть запись. Попробуй ещё раз."
ITEM_NOT_FOUND = "Запись не найдена в твоей библиотеке."
ITEM_ACTION_FAILED = "Не удалось изменить запись. Попробуй ещё раз."
ITEM_DELETED = "Запись удалена из библиотеки."
ITEM_DELETE_PROMPT = "Удалить эту запись из библиотеки?"
ITEM_EDIT_PROMPT = "Что изменить?"
ITEM_MARKED_WATCHED = "Отмечено как просмотренное."
RATING_UPDATED = "Оценка изменена."
RATING_EDIT_CANCELLED = "Изменение оценки отменено."


def library_text(
    items: list,
    bot_username: str,
    offset: int = 0,
    sort_order: str = "recent",
) -> str:
    if not items:
        return (
            f"{LIBRARY_HEADING}\n"
            "╰ <i>Ничего не найдено</i>\n\n"
            "Измени фильтры и попробуй снова."
        )

    heading = {
        "recent": "по дате",
        "rating": "по моей оценке",
        "tmdb_rating": "по оценке TMDB",
        "title": "по названию",
    }.get(sort_order, "по дате")
    lines = [
        LIBRARY_HEADING,
        f"╰ <i>Сортировка {heading}</i>",
        "",
    ]
    for index, item in enumerate(items, start=offset + 1):
        if index > offset + 1:
            lines.append(LIBRARY_ITEM_DIVIDER)
        url = f"https://t.me/{bot_username}?start=media_{int(item['id'])}"
        lines.append(f'<a href="{url}">{index}. {escape(item["title"])}</a>')
        lines.append(_library_item_summary(item))
    return "\n".join(lines)


def _library_item_summary(item) -> str:
    parts: list[str] = []
    status_value = _item_value(item, "user_status")
    if _item_value(item, "content_format") == "series":
        watched = _item_value(item, "episodes_watched", 0) or 0
        total = _item_value(item, "available_episode_count")
        if total is None:
            total = _item_value(item, "number_of_episodes")
        progress = (
            f"{watched} из {total} серий" if total is not None else f"{watched} серий"
        )
        parts.append(progress)
    if status_value is not None:
        status = USER_STATUS_TITLES.get(status_value, status_value)
        parts.append(escape(status))

    user_rating = _item_value(item, "user_rating")
    tmdb_rating = _item_value(item, "rating")
    parts.append(f"Моя · {user_rating}/10" if user_rating is not None else "Моя · —")
    parts.append(
        f"TMDB · {tmdb_rating:.1f}/10" if tmdb_rating is not None else "TMDB · —"
    )
    return " · ".join(parts)


def _item_value(item, name: str, default=None):
    try:
        return item[name]
    except (IndexError, KeyError):
        return default


def library_item_text(item, description: str | None = None) -> str:
    media_kind = MEDIA_KIND_TITLES.get(
        (item["content_format"], item["content_type"]),
        CONTENT_TYPE_TITLES.get(item["content_type"], item["content_type"]),
    )
    user_status = USER_STATUS_TITLES.get(item["user_status"], item["user_status"])
    date_value = item["release_date"] or item["first_air_date"]

    lines = [f"┈┈┈  <b>{escape(item['title'])}</b>  ┈┈┈"]
    if item["original_title"] and item["original_title"] != item["title"]:
        lines.append(f"<i>{escape(item['original_title'])}</i>")
    lines.append(f"<i>{escape(media_kind)}</i>")

    lines.extend(["", "<b>Моя запись</b>"])
    status_icon = USER_STATUS_ICONS.get(item["user_status"], "·")
    lines.append(f"Статус · <b>{status_icon} {escape(user_status)}</b>")
    if item["number_of_episodes"] is not None:
        watched = item["episodes_watched"] or 0
        progress_total = _item_value(
            item,
            "available_episode_count",
            item["number_of_episodes"],
        )
        lines.append(f"Прогресс · <b>{watched} из {progress_total} вышедших серий</b>")
    if item["user_rating"] is not None:
        lines.append(f"Оценка · <b>{item['user_rating']}/10</b>")

    details_heading = "О сериале" if item["content_format"] == "series" else "О фильме"
    lines.extend(["", f"<b>{details_heading}</b>"])
    if item["rating"] is not None:
        lines.append(f"TMDB · <b>{item['rating']:.1f}/10</b>")
    lines.append(f"Добавили · <b>{item['library_users_count']}</b>")
    if date_value:
        lines.append(f"Премьера · <b>{escape(date_value)}</b>")
    if item["number_of_seasons"] is not None:
        lines.append(f"Сезонов · <b>{item['number_of_seasons']}</b>")
    if item["number_of_episodes"] is not None:
        available = _item_value(item, "available_episode_count")
        if available is not None and available != item["number_of_episodes"]:
            lines.append(
                f"Серий · <b>вышло {available} из {item['number_of_episodes']}</b>"
            )
        else:
            lines.append(f"Серий · <b>{item['number_of_episodes']}</b>")
    release_line = _series_release_line(item)
    if release_line is not None:
        lines.append(release_line)

    description_text = (
        item["description"] or DESCRIPTION_NOT_FOUND
        if description is None
        else description
    )
    lines.extend(["", "<b>Описание</b>", escape(description_text)])
    return "\n".join(lines)


def _series_release_line(item) -> str | None:
    if _item_value(item, "content_format") != "series":
        return None
    in_production = _item_value(item, "tmdb_in_production")
    status = _item_value(item, "tmdb_status")
    if not bool(in_production) and status not in ACTIVE_TMDB_SERIES_STATUSES:
        return None

    season_number = _item_value(item, "next_episode_season_number")
    episode_number = _item_value(item, "next_episode_number")
    air_date = _format_air_date(_item_value(item, "next_episode_air_date"))
    if type(season_number) is int and type(episode_number) is int:
        date_suffix = f" · {air_date}" if air_date is not None else ""
        if episode_number == 1:
            detail = f"Новый сезон · <b>{season_number} сезон{date_suffix}</b>"
        else:
            detail = (
                "Следующая серия · "
                f"<b>{season_number} сезон, {episode_number} серия{date_suffix}</b>"
            )
    else:
        detail = "Новые серии · <b>дата пока неизвестна</b>"
    return f"🔴 <b>Сейчас выходит</b>\n{detail}"


def _format_air_date(value) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value).strftime("%d.%m.%Y")
    except ValueError:
        return escape(value)


__all__ = (
    "FILTER_SAVE_FAILED",
    "INVALID_PAGE",
    "ITEM_NOT_FOUND",
    "ITEM_OPEN_FAILED",
    "ITEM_ACTION_FAILED",
    "ITEM_DELETED",
    "ITEM_DELETE_PROMPT",
    "ITEM_EDIT_PROMPT",
    "ITEM_MARKED_WATCHED",
    "LIBRARY_OPEN_FAILED",
    "UNKNOWN_FILTER",
    "RATING_UPDATED",
    "RATING_EDIT_CANCELLED",
    "USER_STATUS_TITLES",
    "library_item_text",
    "library_text",
)
