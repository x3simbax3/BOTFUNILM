MAIN_LIBRARY = "♡\u00a0Моя библиотека"
MAIN_SETTINGS = "⚙\u00a0Настройки"
MAIN_TRACKED = "◉\u00a0Отслеживаемые"
MAIN_ADD = "＋\u00a0Добавить"
MAIN_NEWS_ON = "★\u00a0Новости · вкл"
MAIN_NEWS_OFF = "★\u00a0Новости · выкл"
LIBRARY_ALL = "♡\u00a0Все сохранённые"

FILTER_SERIES = "Сериалы"
FILTER_FULL_LENGTH = "Полный метр"
FILTER_ANIME = "Аниме"
FILTER_MOVIES = "Кино"
FILTER_CARTOONS = "Мультфильмы"
FILTER_RECENT = "По дате"
SORT_RATING = "Моя оценка"
RESET_FILTERS = "↺\u00a0Сбросить всё"
FILTER_COMPLETED = "Просмотрено"
FILTER_PLANNED = "Хочу посмотреть"
FILTER_UNFINISHED = "Не досмотрено"
FILTER_ONGOING = "Сейчас выходит"
FILTER_ALL = "Все"
FILTER_FORMAT_GROUP = "▤\u00a0Формат"
FILTER_CATEGORY_GROUP = "◇\u00a0Категория"
FILTER_STATUS_GROUP = "◉\u00a0Прогресс"
FILTER_SORT_GROUP = "⇅\u00a0Сортировка"
SORT_TMDB_RATING = "Оценка TMDB"
SORT_TITLE = "По названию"
FILTERS_BACK = "‹\u00a0К фильтрам"

BACK = "‹\u00a0Назад"
PREVIOUS_PAGE = "‹\u00a0Пред. страница"
NEXT_PAGE = "След. страница\u00a0›"
TO_MENU = "⌂\u00a0Главное меню"
TO_LIBRARY = "‹\u00a0В библиотеку"
EDIT_ITEM = "✎\u00a0Изменить"
DELETE_ITEM = "×\u00a0Удалить"
MARK_WATCHED = "✓\u00a0Отметить просмотренным"
EDIT_RATING = "★\u00a0Изменить оценку"
EDIT_PROGRESS = "▣\u00a0Изменить прогресс"
EDIT_BADGE = "☺\u00a0Изменить лычку"
TRACKING_ENABLE = "＋\u00a0Отслеживать"
TRACKING_DISABLE = "×\u00a0Не отслеживать"
TRACKING_ACTIVE = "Активно"
TRACKING_INACTIVE = "Не активно"
CONFIRM_DELETE = "×\u00a0Да, удалить"
CANCEL = "Отмена"
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
ALL_SEASONS = "▣\u00a0Все сезоны"
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
