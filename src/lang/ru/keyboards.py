MAIN_LIBRARY = "📚 Библиотека"
MAIN_ADD = "➕ Добавить"

FILTER_SERIES = "📺 Сериалы"
FILTER_FULL_LENGTH = "🎬 Полный метр"
FILTER_ANIME = "✨ Аниме"
FILTER_MOVIES = "🎥 Фильмы"
FILTER_CARTOONS = "🧸 Мульты"
FILTER_ALL = "Все"
SORT_RATING = "⭐ Топ"

BACK = "⬅️ Назад"
MORE = "Ещё ➡️"
TO_MENU = "🏠 В меню"
TO_LIBRARY = "⬅️ К библиотеке"
FORMAT_FULL_LENGTH = "🎬 Полный метр"
FORMAT_SERIES = "📺 Сериалы"
TYPE_MOVIE = "🎥 Фильм"
TYPE_ANIME = "✨ Аниме"
TYPE_CARTOON = "🧸 Мультфильм"
GUESS_YES = "✅ Да, это он"
GUESS_NO = "❌ Нет"
ANOTHER_TITLE = "🔎 Другое название"
ANOTHER_CATEGORY = "🔁 Другая категория"
SAVE = "✅ Сохранить"
SAVE_PROGRESS = "✅ Сохранить прогресс"


def selected(label: str, is_selected: bool) -> str:
    return f"✅ {label}" if is_selected else label


def season_progress(name: str, watched: int, total: int) -> str:
    return f"{name}  ·  {watched}/{total}"


__all__ = tuple(name for name in globals() if name.isupper()) + (
    "season_progress",
    "selected",
)
