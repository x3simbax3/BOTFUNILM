from html import escape

from .common import DESCRIPTION_NOT_FOUND
from .menu import FORMAT_RESULT_TITLES

TMDB_SEARCHING = "⌕ Ищу по названию…"
TMDB_SEARCHING_REMOTE = "⌕ Проверяю каталог TMDB…"
TMDB_TOO_LONG = "⚠️ Слишком длинное название. Сократи и попробуй снова."
TITLE_AS_TEXT = "Введи название текстом."
TITLE_EMPTY = "Название не может быть пустым. Введи название ещё раз."
FORMAT_MISSING = "Не найден выбранный формат. Начни заново через /start."
LOCAL_SEARCH_FAILED = "Не удалось проверить локальный каталог. Попробуй ещё раз."
STALE_GUESS = "Это старый вариант."
REJECTED_GUESS = "Не тот результат. Измени название или категорию."
TMDB_NOT_CONFIGURED = "TMDB_API не настроен. Добавь ключ в config/.env."
TMDB_AUTH_FAILED = "TMDB отклонил ключ доступа. Проверь настройку TMDB_API."
TMDB_RATE_LIMITED = "TMDB временно ограничил запросы. Попробуй через минуту."
TMDB_UNAVAILABLE = "TMDB сейчас недоступен. Попробуй немного позже."
TMDB_FAILED = "Не удалось получить ответ от TMDB. Попробуй позже."
INVALID_WATCH_STATUS = "Неизвестный статус просмотра"
TITLE_SAVE_FAILED = "Не удалось сохранить. Попробуй ещё раз."
ALREADY_IN_LIBRARY = "Уже добавлено в библиотеку"
WATCH_STATUS_PROMPT = (
    "━━━  <b>Добавление</b>  ━━━\n"
    "<i>Шаг 4 из 4 · Статус</i>\n\n"
    "Уже посмотрено или сохранить на потом?"
)


def tmdb_guess_text(content_format: str, title: str, overview: str | None) -> str:
    description = overview or DESCRIPTION_NOT_FOUND
    return (
        "━━━  ⌕ <b>Результат поиска</b>  ━━━\n\n"
        f"<b>{escape(title)}</b>\n"
        f"<i>{FORMAT_RESULT_TITLES[content_format]}</i>\n\n"
        f"<blockquote>{escape(description)}</blockquote>\n\n"
        "Это то, что ты искал?"
    )


def tmdb_found_text(title: str) -> str:
    return f"✓ Найдено · <b>{escape(title)}</b>"


def tmdb_not_found_text(query: str) -> str:
    return (
        f'😕 Ничего не нашёл по запросу <b>"{escape(query)}"</b>.\n'
        "Попробуй ввести название иначе."
    )


def planned_title_saved_text(title: str) -> str:
    return (
        "✓ <b>Добавлено в библиотеку</b>\n\n"
        f"<b>{escape(title)}</b>\n"
        "Статус · <b>Хочу посмотреть</b>"
    )


__all__ = (
    "ALREADY_IN_LIBRARY",
    "FORMAT_MISSING",
    "INVALID_WATCH_STATUS",
    "LOCAL_SEARCH_FAILED",
    "REJECTED_GUESS",
    "STALE_GUESS",
    "TITLE_AS_TEXT",
    "TITLE_EMPTY",
    "TITLE_SAVE_FAILED",
    "TMDB_AUTH_FAILED",
    "TMDB_FAILED",
    "TMDB_NOT_CONFIGURED",
    "TMDB_RATE_LIMITED",
    "TMDB_SEARCHING",
    "TMDB_SEARCHING_REMOTE",
    "TMDB_TOO_LONG",
    "TMDB_UNAVAILABLE",
    "WATCH_STATUS_PROMPT",
    "planned_title_saved_text",
    "tmdb_found_text",
    "tmdb_guess_text",
    "tmdb_not_found_text",
)
