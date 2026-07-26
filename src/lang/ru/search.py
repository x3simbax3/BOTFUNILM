from html import escape

from .common import DESCRIPTION_NOT_FOUND
from .menu import FORMAT_RESULT_TITLES


TMDB_SEARCHING = "🔍 Ищу в каталоге..."
TMDB_SEARCHING_REMOTE = "🔍 В каталоге не найдено, ищу в TMDB..."
TMDB_TOO_LONG = "⚠️ Слишком длинное название. Сократи и попробуй снова."
TITLE_AS_TEXT = "Введи название текстом."
TITLE_EMPTY = "Название не может быть пустым. Введи название ещё раз."
FORMAT_MISSING = "Не найден выбранный формат. Начни заново через /start."
LOCAL_SEARCH_FAILED = "Не удалось проверить локальный каталог. Попробуй ещё раз."
STALE_GUESS = "Это старый вариант."
REJECTED_GUESS = "Ок, не оно. Что сделать?"
TMDB_NOT_CONFIGURED = "TMDB_API не настроен. Добавь ключ в config/.env."
TMDB_AUTH_FAILED = "TMDB отклонил ключ доступа. Проверь настройку TMDB_API."
TMDB_RATE_LIMITED = "TMDB временно ограничил запросы. Попробуй через минуту."
TMDB_UNAVAILABLE = "TMDB сейчас недоступен. Попробуй немного позже."
TMDB_FAILED = "Не удалось получить ответ от TMDB. Попробуй позже."


def tmdb_guess_text(content_format: str, title: str, overview: str | None) -> str:
    description = overview or DESCRIPTION_NOT_FOUND
    return (
        "<b>Проверь результат</b>\n\n"
        f"🎬 <b>{escape(title)}</b>\n"
        f"<i>{FORMAT_RESULT_TITLES[content_format]}</i>\n\n"
        f"{escape(description)}\n\n"
        "<b>Это нужный тайтл?</b>"
    )


def tmdb_found_text(title: str) -> str:
    return f"✅ Нашёл: <b>{escape(title)}</b>"


def tmdb_not_found_text(query: str) -> str:
    return (
        f'😕 Ничего не нашёл по запросу <b>"{escape(query)}"</b>.\n'
        "Попробуй ввести название иначе."
    )


__all__ = (
    "FORMAT_MISSING",
    "LOCAL_SEARCH_FAILED",
    "REJECTED_GUESS",
    "STALE_GUESS",
    "TITLE_AS_TEXT",
    "TITLE_EMPTY",
    "TMDB_AUTH_FAILED",
    "TMDB_FAILED",
    "TMDB_NOT_CONFIGURED",
    "TMDB_RATE_LIMITED",
    "TMDB_SEARCHING",
    "TMDB_SEARCHING_REMOTE",
    "TMDB_TOO_LONG",
    "TMDB_UNAVAILABLE",
    "tmdb_found_text",
    "tmdb_guess_text",
    "tmdb_not_found_text",
)
