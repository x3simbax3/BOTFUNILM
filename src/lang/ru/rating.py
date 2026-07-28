from datetime import date
from html import escape

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

INVALID_RATING = "Некорректная оценка"
RATING_ALREADY_SAVED = "Эта оценка уже сохранена"
MOVIE_SAVE_FAILED = "Не удалось сохранить фильм. Попробуй ещё раз."


def rating_categories(content_type: str) -> list[tuple[str, str]]:
    if content_type in {"anime", "cartoon"}:
        return ANIMATION_RATING_CATEGORIES
    return RATING_CATEGORIES


def rating_prompt_text(
    title: str,
    category_name: str,
    category_number: int,
    total: int,
) -> str:
    return (
        f"━━━  ★ <b>{escape(title)}</b>  ━━━\n"
        f"<i>Критерий {category_number} из {total}</i>\n\n"
        f"<b>{category_name}</b>\n"
        "Выбери оценку от 1 до 10"
    )


def rating_summary_text(
    title: str,
    ratings: dict[str, int],
    average: float,
    categories: list[tuple[str, str]] | None = None,
) -> str:
    lines = [
        f"━━━  ✓ <b>{escape(title)}</b>  ━━━",
        "<i>Оценка сохранена</i>",
        "",
    ]
    for key, name in categories or RATING_CATEGORIES:
        score = ratings.get(key, "-")
        lines.append(f"{name} · <b>{score}/10</b>")
    lines.append(f"\n★ <b>Итоговая оценка · {average:.1f}/10</b>")
    lines.append(f"<i>{_today()}</i>")
    return "\n".join(lines)


def movie_watched_text(title: str, average: float) -> str:
    return (
        "✓ <b>Добавлено в библиотеку</b>\n\n"
        f"🎞 <b>{escape(title)}</b>\n"
        f"Моя оценка · <b>{average:.1f}/10</b>\n"
        f"<i>{_today()}</i>"
    )


def _today() -> str:
    return date.today().strftime("%d.%m.%Y")


__all__ = (
    "ANIMATION_RATING_CATEGORIES",
    "INVALID_RATING",
    "MOVIE_SAVE_FAILED",
    "RATING_ALREADY_SAVED",
    "RATING_CATEGORIES",
    "movie_watched_text",
    "rating_categories",
    "rating_prompt_text",
    "rating_summary_text",
)
