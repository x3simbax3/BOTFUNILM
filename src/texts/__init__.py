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

RATING_CATEGORIES = [
    ("acting", "Актерская игра"),
    ("story", "Сюжет"),
    ("visuals", "Визуал"),
    ("sound", "Звук/Музыка"),
    ("overall", "Общее впечатление"),
]


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
        "Введи название, а я сначала проверю каталог, затем TMDB."
    )


def tmdb_guess_text(content_format: str, title: str, overview: str | None) -> str:
    description = overview or "Описание не найдено."
    return (
        "Ты имеешь в виду:\n\n"
        f"<b>{FORMAT_RESULT_TITLES[content_format]} {escape(title)}</b>\n\n"
        f"{escape(description)}"
    )


TMDB_SEARCHING = "🔍 Ищу в каталоге..."

TMDB_TOO_LONG = "⚠️ Слишком длинное название. Сократи и попробуй снова."


def tmdb_found_text(title: str) -> str:
    return f"🎯 Нашёл: <b>{escape(title)}</b>"


def tmdb_not_found_text(query: str) -> str:
    return (
        f"😕 Ничего не нашёл по запросу <b>\"{escape(query)}\"</b>.\n"
        "Попробуй ввести название иначе."
    )


def rating_prompt_text(title: str, category_name: str, category_number: int, total: int) -> str:
    return (
        f"Оцени <b>{escape(title)}</b>\n"
        f"Категория {category_number}/{total}: <b>{category_name}</b>\n\n"
        "Поставь оценку от 1 до 10:"
    )


def rating_summary_text(title: str, ratings: dict[str, int], average: float) -> str:
    lines = [f"Оценки для <b>{escape(title)}</b>:\n"]
    for key, name in RATING_CATEGORIES:
        score = ratings.get(key, "-")
        lines.append(f"  {name}: <b>{score}</b>")
    lines.append(f"\n<b>Средняя оценка: {average:.1f}</b>")
    lines.append(f"\nДата: {_today()}")
    return "\n".join(lines)


def series_tracking_text(title: str, seasons: list[dict]) -> str:
    lines = [f"Сериал <b>{escape(title)}</b>:\n"]
    for s in seasons:
        lines.append(
            f"  {s['name']}: {s['episode_count']} серий"
        )
    lines.append("\nВыбери сезон и укажи, сколько серий посмотрел:")
    return "\n".join(lines)


def episodes_prompt_text(title: str, season_name: str, total_episodes: int, already_watched: int) -> str:
    remaining = total_episodes - already_watched
    return (
        f"<b>{escape(title)}</b> — {season_name}\n"
        f"Всего серий: {total_episodes}, уже посмотрено: {already_watched}\n"
        f"Осталось: {remaining}\n\n"
        "Сколько серий посмотрел в этом сезоне?"
    )


def tracking_complete_text(
    title: str,
    total_episodes: int,
    watched_episodes: int,
    average: float,
) -> str:
    remaining = total_episodes - watched_episodes
    status = "досмотрен" if remaining == 0 else f"осталось {remaining} серий"
    return (
        f"<b>{escape(title)}</b>\n\n"
        f"Просмотрено: {watched_episodes}/{total_episodes} серий\n"
        f"Статус: {status}\n"
        f"Средняя оценка: {average:.1f}\n"
        f"Дата: {_today()}"
    )


def movie_watched_text(title: str, average: float) -> str:
    return (
        f"Фильм <b>{escape(title)}</b> отмечен как просмотренный.\n"
        f"Средняя оценка: {average:.1f}\n"
        f"Дата: {_today()}"
    )


def _today() -> str:
    from datetime import date
    return date.today().strftime("%d.%m.%Y")


__all__ = (
    "ACTION_TITLES",
    "BOT_NAME",
    "CONTENT_TYPE_TITLES",
    "FORMAT_RESULT_TITLES",
    "FORMAT_TITLES",
    "RATING_CATEGORIES",
    "START_TEXT",
    "TMDB_SEARCHING",
    "TMDB_TOO_LONG",
    "action_text",
    "content_type_text",
    "episodes_prompt_text",
    "movie_watched_text",
    "rating_prompt_text",
    "rating_summary_text",
    "selected_type_text",
    "series_tracking_text",
    "tmdb_found_text",
    "tmdb_guess_text",
    "tmdb_not_found_text",
    "tracking_complete_text",
)
