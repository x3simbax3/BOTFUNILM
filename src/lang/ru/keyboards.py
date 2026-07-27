MAIN_LIBRARY = "♡\u00a0Моя библиотека"
MAIN_ADD = "＋\u00a0Добавить"

FILTER_SERIES = "Сериалы"
FILTER_FULL_LENGTH = "Полный метр"
FILTER_ANIME = "Аниме"
FILTER_MOVIES = "Кино"
FILTER_CARTOONS = "Мультфильмы"
FILTER_RECENT = "По дате"
SORT_RATING = "По оценке"
RESET_FILTERS = "↺\u00a0Показать всё"
FILTER_COMPLETED = "Просмотрено"
FILTER_PLANNED = "Хочу посмотреть"

BACK = "‹\u00a0Назад"
PREVIOUS_PAGE = "‹\u00a0Пред. страница"
NEXT_PAGE = "След. страница\u00a0›"
TO_MENU = "⌂\u00a0Главное меню"
TO_LIBRARY = "‹\u00a0В библиотеку"
FORMAT_FULL_LENGTH = "▤\u00a0Фильм"
FORMAT_SERIES = "▣\u00a0Сериал"
TYPE_MOVIE = "◈\u00a0Кино"
TYPE_ANIME = "✦\u00a0Аниме"
TYPE_CARTOON = "◇\u00a0Мультфильм"
GUESS_YES = "✓\u00a0Да, это он"
GUESS_NO = "×\u00a0Нет, другой"
ANOTHER_TITLE = "⌕\u00a0Изменить название"
ANOTHER_CATEGORY = "◇\u00a0Категория и формат"
SAVE = "✓\u00a0Сохранить"
SAVE_PROGRESS = "✓\u00a0Сохранить прогресс"
ALL_EPISODES = "✓\u00a0Все серии"
STATUS_COMPLETED = "✓\u00a0Уже просмотрено"
STATUS_PLANNED = "♡\u00a0Хочу посмотреть"


def selected(label: str, is_selected: bool) -> str:
    return f"✓\u00a0{label}" if is_selected else label


def season_progress(name: str, watched: int, total: int) -> str:
    return f"{name}  ·  {watched} из {total}"


__all__ = tuple(name for name in globals() if name.isupper()) + (
    "season_progress",
    "selected",
)
