from html import escape

from .common import DESCRIPTION_NOT_FOUND
from .menu import CONTENT_TYPE_TITLES, FORMAT_TITLES

USER_STATUS_TITLES = {
    "planned": "Запланировано",
    "watching": "Смотрю",
    "completed": "Просмотрено",
    "on_hold": "Отложено",
    "dropped": "Брошено",
}

UNKNOWN_FILTER = "Неизвестный фильтр"
FILTER_SAVE_FAILED = "Не удалось сохранить фильтр"
INVALID_PAGE = "Некорректная страница"
LIBRARY_OPEN_FAILED = "Не удалось открыть библиотеку"
ITEM_OPEN_FAILED = "Не удалось открыть тайтл. Попробуй ещё раз."
ITEM_NOT_FOUND = "Тайтл не найден в твоей библиотеке."


def library_text(
    items: list,
    bot_username: str,
    offset: int = 0,
    sort_order: str = "recent",
) -> str:
    if not items:
        return "<b>Моя библиотека 📚</b>\n\nПо выбранным фильтрам ничего не найдено."

    heading = (
        "Тайтлы с высокой оценкой:"
        if sort_order == "rating"
        else "Последние добавленные тайтлы:"
    )
    lines = ["<b>Моя библиотека 📚</b>", "", heading]
    for index, item in enumerate(items, start=offset + 1):
        url = f"https://t.me/{bot_username}?start=media_{int(item['id'])}"
        lines.append(f'{index}. <a href="{url}">{escape(item["title"])}</a>')
    return "\n".join(lines)


def library_item_text(item, description: str | None = None) -> str:
    content_format = FORMAT_TITLES.get(item["content_format"], item["content_format"])
    content_type = CONTENT_TYPE_TITLES.get(item["content_type"], item["content_type"])
    user_status = USER_STATUS_TITLES.get(item["user_status"], item["user_status"])
    date_value = item["release_date"] or item["first_air_date"]

    lines = [
        f"🎬 <b>{escape(item['title'])}</b>",
        f"<i>{escape(content_format)} · {escape(content_type)}</i>",
    ]
    if item["original_title"] and item["original_title"] != item["title"]:
        lines.append(f"Оригинал: <i>{escape(item['original_title'])}</i>")

    lines.extend(["", f"Статус: <b>{escape(user_status)}</b>"])
    if item["user_rating"] is not None:
        lines.append(f"Моя оценка: <b>{item['user_rating']}/10</b>")
    if item["rating"] is not None:
        lines.append(f"Рейтинг TMDB: <b>{item['rating']:.1f}/10</b>")
    if date_value:
        lines.append(f"Дата выхода: <b>{escape(date_value)}</b>")
    if item["number_of_seasons"] is not None:
        lines.append(f"Сезонов: <b>{item['number_of_seasons']}</b>")
    if item["number_of_episodes"] is not None:
        watched = item["episodes_watched"] or 0
        lines.append(
            f"Серий просмотрено: <b>{watched}/{item['number_of_episodes']}</b>"
        )

    description_text = (
        item["description"] or DESCRIPTION_NOT_FOUND
        if description is None
        else description
    )
    lines.extend(["", escape(description_text)])
    return "\n".join(lines)


__all__ = (
    "FILTER_SAVE_FAILED",
    "INVALID_PAGE",
    "ITEM_NOT_FOUND",
    "ITEM_OPEN_FAILED",
    "LIBRARY_OPEN_FAILED",
    "UNKNOWN_FILTER",
    "USER_STATUS_TITLES",
    "library_item_text",
    "library_text",
)
