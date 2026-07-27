MAIN_LIBRARY = "Моя библиотека"
MAIN_ADD = "Добавить"

FILTER_SERIES = "Сериалы"
FILTER_FULL_LENGTH = "Полный метр"
FILTER_ANIME = "Аниме"
FILTER_MOVIES = "Кино"
FILTER_CARTOONS = "Мультфильмы"
FILTER_RECENT = "По дате"
SORT_RATING = "По оценке"
RESET_FILTERS = "Сбросить фильтры"
FILTER_COMPLETED = "Просмотрено"
FILTER_PLANNED = "Хочу посмотреть"

BACK = "← Назад"
MORE = "Дальше →"
TO_MENU = "⌂ Главное меню"
TO_LIBRARY = "← В библиотеку"
FORMAT_FULL_LENGTH = "Фильм"
FORMAT_SERIES = "Сериал"
TYPE_MOVIE = "Кино"
TYPE_ANIME = "Аниме"
TYPE_CARTOON = "Мультфильм"
GUESS_YES = "✓ Да, это он"
GUESS_NO = "Нет, другой"
ANOTHER_TITLE = "⌕ Изменить название"
ANOTHER_CATEGORY = "Категория и формат"
SAVE = "Сохранить"
SAVE_PROGRESS = "✓ Сохранить прогресс"
STATUS_COMPLETED = "✓ Уже просмотрено"
STATUS_PLANNED = "＋ Хочу посмотреть"


def selected(label: str, is_selected: bool) -> str:
    return f"✓ {label}" if is_selected else label


def season_progress(name: str, watched: int, total: int) -> str:
    return f"{name}  ·  {watched} из {total}"


__all__ = tuple(name for name in globals() if name.isupper()) + (
    "season_progress",
    "selected",
)
