from html import escape

BOT_NAME = "BotFunilm"

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

RATING_CATEGORIES = [
    ("acting", "Актёрская игра"),
    ("story", "Сюжет"),
    ("visuals", "Визуал"),
    ("sound", "Звук и музыка"),
    ("overall", "Общее впечатление"),
]

ANIMATION_RATING_CATEGORIES = [
    ("animation", "Анимация"),
    ("story", "Сюжет"),
    ("characters", "Персонажи"),
    ("sound", "Музыка и озвучка"),
    ("overall", "Общее впечатление"),
]


def rating_categories(content_type: str) -> list[tuple[str, str]]:
    if content_type in {"anime", "cartoon"}:
        return ANIMATION_RATING_CATEGORIES
    return RATING_CATEGORIES


def action_text(action: str) -> str:
    if action == "library":
        return (
            f"<b>{ACTION_TITLES[action]} 📚</b>\n\n"
            "Выбери формат:"
        )

    return (
        f"<b>{ACTION_TITLES[action]} ➕</b>\n\n"
        "Выбери формат:"
    )


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


def tmdb_guess_text(content_format: str, title: str, overview: str | None) -> str:
    description = overview or "Описание не найдено."
    return (
        "<b>Проверь результат</b>\n\n"
        f"🎬 <b>{escape(title)}</b>\n"
        f"<i>{FORMAT_RESULT_TITLES[content_format]}</i>\n\n"
        f"{escape(description)}\n\n"
        "<b>Это нужный тайтл?</b>"
    )


TMDB_SEARCHING = "🔍 Ищу в каталоге..."

TMDB_TOO_LONG = "⚠️ Слишком длинное название. Сократи и попробуй снова."


def tmdb_found_text(title: str) -> str:
    return f"✅ Нашёл: <b>{escape(title)}</b>"


def tmdb_not_found_text(query: str) -> str:
    return (
        f"😕 Ничего не нашёл по запросу <b>\"{escape(query)}\"</b>.\n"
        "Попробуй ввести название иначе."
    )


def rating_prompt_text(title: str, category_name: str, category_number: int, total: int) -> str:
    return (
        f"<b>Оцениваем «{escape(title)}»</b>\n\n"
        f"{category_number}/{total} · <b>{category_name}</b>\n"
        "Выбери оценку от 1 до 10:"
    )


def rating_summary_text(
    title: str,
    ratings: dict[str, int],
    average: float,
    categories: list[tuple[str, str]] | None = None,
) -> str:
    lines = [f"<b>Оценки «{escape(title)}»</b> ✅\n"]
    for key, name in categories or RATING_CATEGORIES:
        score = ratings.get(key, "-")
        lines.append(f"• {name}: <b>{score}/10</b>")
    lines.append(f"\n⭐ <b>Итог: {average:.1f}/10</b>")
    lines.append(f"📅 {_today()}")
    return "\n".join(lines)


def series_tracking_text(title: str, seasons: list[dict]) -> str:
    lines = [f"📺 <b>{escape(title)}</b>\n"]
    for s in seasons:
        lines.append(
            f"• {escape(s['name'])} — {s['episode_count']} серий"
        )
    lines.append("\n<b>Выбери сезон</b>, чтобы отметить прогресс:")
    return "\n".join(lines)


def episodes_prompt_text(title: str, season_name: str, total_episodes: int, already_watched: int) -> str:
    remaining = total_episodes - already_watched
    return (
        f"<b>{escape(title)}</b>\n"
        f"<blockquote>{escape(season_name)}</blockquote>\n"
        f"✅ Просмотрено: <b>{already_watched}/{total_episodes}</b>\n"
        f"⏳ Осталось: <b>{remaining}</b>\n\n"
        "Укажи, сколько серий уже посмотрено:"
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
        "<b>Прогресс сохранён ✅</b>\n\n"
        f"📺 <b>{escape(title)}</b>\n"
        f"Просмотрено: <b>{watched_episodes}/{total_episodes}</b>\n"
        f"Статус: <b>{status}</b>\n"
        f"⭐ Оценка: <b>{average:.1f}/10</b>\n"
        f"📅 {_today()}"
    )


def movie_watched_text(title: str, average: float) -> str:
    return (
        "<b>Фильм сохранён ✅</b>\n\n"
        f"🎬 <b>{escape(title)}</b>\n"
        f"⭐ Оценка: <b>{average:.1f}/10</b>\n"
        f"📅 {_today()}"
    )


def _today() -> str:
    from datetime import date
    return date.today().strftime("%d.%m.%Y")


__all__ = (
    "ACTION_TITLES",
    "ANIMATION_RATING_CATEGORIES",
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
    "rating_categories",
    "rating_summary_text",
    "selected_type_text",
    "series_tracking_text",
    "tmdb_found_text",
    "tmdb_guess_text",
    "tmdb_not_found_text",
    "tracking_complete_text",
)
