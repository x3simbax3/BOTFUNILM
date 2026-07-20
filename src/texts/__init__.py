from html import escape

BOT_NAME = "BotFunilm"

START_TEXT = f"""<b>{BOT_NAME} 🍿</b>

<blockquote>Твоя личная полка для фильмов, аниме, мультфильмов и сериалов.
Сюда можно складывать то, что уже посмотрел, и то, до чего руки ещё не дошли.</blockquote>

<b>Что можно сделать:</b>
• <b>Библиотека</b> — открыть уже сохранённое
• <b>Добавить</b> — начать добавлять новый тайтл

<i>Пока меню работает как навигация: выбираешь раздел, формат и тип. Я запомню выбор и поведу дальше.</i>
"""

ACTION_TITLES = {
    "library": "Моя библиотека",
    "add": "Добавить",
}

FORMAT_TITLES = {
    "full_length": "полнометражки",
    "series": "сериалы",
}

FORMAT_RESULT_TITLES = {
    "full_length": "Фильм",
    "series": "Сериал",
}

CONTENT_TYPE_TITLES = {
    "movie": "фильмы",
    "anime": "аниме",
    "cartoon": "мультфильмы",
}


def action_text(action: str) -> str:
    if action == "library":
        return (
            f"<b>{ACTION_TITLES[action]} 📚</b>\n\n"
            "Сначала сузим полку, чтобы не мешать всё в одну кучу.\n"
            "Что хочешь открыть?"
        )

    return (
        f"<b>{ACTION_TITLES[action]} ➕</b>\n\n"
        "Сначала выберем формат, а потом тип тайтла.\n"
        "Что добавляем?"
    )


def content_type_text(action: str, content_format: str) -> str:
    action_hint = (
        "Теперь уточним, что искать в библиотеке."
        if action == "library"
        else "Теперь уточним, что именно добавляем."
    )

    return (
        f"<b>{ACTION_TITLES[action]}</b>\n\n"
        f"Формат: <b>{FORMAT_TITLES[content_format]}</b>.\n"
        f"{action_hint}\n\n"
        "Выбери тип:"
    )


def selected_type_text(action: str, content_format: str, content_type: str) -> str:
    return (
        f"<b>{ACTION_TITLES[action]}</b>\n\n"
        "Выбор сохранён ✅\n"
        f"<blockquote>{FORMAT_TITLES[content_format]} / "
        f"{CONTENT_TYPE_TITLES[content_type]}</blockquote>\n"
        "Введи название, а я найду самый похожий вариант в TMDB."
    )


def tmdb_guess_text(content_format: str, title: str, overview: str | None) -> str:
    description = overview or "Описание не найдено."
    return (
        "Ты имеешь в виду:\n\n"
        f"<b>{FORMAT_RESULT_TITLES[content_format]} {escape(title)}</b>\n\n"
        f"{escape(description)}"
    )


__all__ = (
    "ACTION_TITLES",
    "BOT_NAME",
    "CONTENT_TYPE_TITLES",
    "FORMAT_RESULT_TITLES",
    "FORMAT_TITLES",
    "START_TEXT",
    "action_text",
    "content_type_text",
    "selected_type_text",
    "tmdb_guess_text",
)
