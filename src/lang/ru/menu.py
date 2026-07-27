from .common import BOT_NAME

START_TEXT = f"""<b>{BOT_NAME}</b>
<i>Фильмы и сериалы — в одном месте</i>

Сохраняй просмотренное, отмечай серии и собирай собственный рейтинг.

<b>Выбери действие</b>"""

ACTION_TITLES = {
    "library": "Моя библиотека",
    "add": "Добавление",
}

FORMAT_TITLES = {
    "full_length": "Полный метр",
    "series": "Сериалы",
}

FORMAT_RESULT_TITLES = {
    "full_length": "Фильм",
    "series": "Сериал",
}

CONTENT_TYPE_TITLES = {
    "movie": "Фильм",
    "anime": "Аниме",
    "cartoon": "Мультфильм",
}

INVALID_SELECTION = "Некорректный выбор"
SELECTION_SAVED = "Выбор сохранен"
ENTER_TITLE_AGAIN = "Введи название ещё раз."
UNKNOWN_STEP = "Неизвестный шаг"
BACK_FAILED = "Не удалось вернуться назад"


def action_text(action: str) -> str:
    return (
        f"<b>{ACTION_TITLES[action]}</b>\n"
        "<i>Шаг 1 из 4 · Формат</i>\n\n"
        "Выбери фильм или сериал"
    )


def content_type_text(action: str, content_format: str) -> str:
    return (
        f"<b>{ACTION_TITLES[action]}</b>\n"
        "<i>Шаг 2 из 4 · Категория</i>\n\n"
        f"Выбрано · <b>{FORMAT_TITLES[content_format]}</b>\n\n"
        "Выбери категорию"
    )


def selected_type_text(action: str, content_format: str, content_type: str) -> str:
    return (
        f"<b>{ACTION_TITLES[action]}</b>\n"
        "<i>Шаг 3 из 4 · Название</i>\n\n"
        f"{FORMAT_TITLES[content_format]} · {CONTENT_TYPE_TITLES[content_type]}\n\n"
        "<b>Введи название</b>\n"
        "<i>На русском или языке оригинала</i>"
    )


__all__ = (
    "ACTION_TITLES",
    "BACK_FAILED",
    "CONTENT_TYPE_TITLES",
    "ENTER_TITLE_AGAIN",
    "FORMAT_RESULT_TITLES",
    "FORMAT_TITLES",
    "INVALID_SELECTION",
    "SELECTION_SAVED",
    "START_TEXT",
    "UNKNOWN_STEP",
    "action_text",
    "content_type_text",
    "selected_type_text",
)
