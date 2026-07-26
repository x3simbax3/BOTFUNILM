from .common import BOT_NAME


START_TEXT = f"""<b>{BOT_NAME} 🍿</b>

<blockquote>Твоя личная коллекция фильмов, сериалов, аниме и мультфильмов.</blockquote>

📚 <b>Библиотека</b> — открыть сохранённое
➕ <b>Добавить</b> — найти и сохранить тайтл

<b>С чего начнём?</b>
"""

ACTION_TITLES = {
    "library": "Моя библиотека",
    "add": "Новый тайтл",
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
    icon = "📚" if action == "library" else "➕"
    return f"<b>{ACTION_TITLES[action]} {icon}</b>\n\nВыбери формат:"


def content_type_text(action: str, content_format: str) -> str:
    return (
        f"<b>{ACTION_TITLES[action]}</b>\n\n"
        f"<blockquote>{FORMAT_TITLES[content_format]}</blockquote>\n"
        "Выбери категорию:"
    )


def selected_type_text(action: str, content_format: str, content_type: str) -> str:
    return (
        f"<b>{ACTION_TITLES[action]}</b>\n\n"
        f"<blockquote>{FORMAT_TITLES[content_format]} · "
        f"{CONTENT_TYPE_TITLES[content_type]}</blockquote>\n"
        "🔎 <b>Введи название</b>\n"
        "Можно на русском или английском."
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
