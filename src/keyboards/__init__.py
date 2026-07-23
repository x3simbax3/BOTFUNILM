from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📚 Библиотека", callback_data="menu:library"),
                InlineKeyboardButton(text="➕ Добавить", callback_data="menu:add"),
            ],
        ],
    )


def format_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎬 Полный метр",
                    callback_data=f"format:{action}:full_length",
                ),
                InlineKeyboardButton(
                    text="📺 Сериалы",
                    callback_data=f"format:{action}:series",
                ),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back:main")],
        ],
    )


def content_type_keyboard(action: str, content_format: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎥 Фильм",
                    callback_data=f"type:{action}:{content_format}:movie",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🌸 Аниме",
                    callback_data=f"type:{action}:{content_format}:anime",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🧸 Мультфильмы",
                    callback_data=f"type:{action}:{content_format}:cartoon",
                ),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back:format:{action}")],
        ],
    )


def selected_type_keyboard(action: str, content_format: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=f"back:content_type:{action}:{content_format}",
                ),
            ],
        ],
    )


def tmdb_guess_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="tmdb_guess:yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data="tmdb_guess:no"),
            ],
        ],
    )


def tmdb_retry_keyboard(
    action: str | None = None,
    content_format: str | None = None,
) -> InlineKeyboardMarkup:
    back_callback = (
        f"back:content_type:{action}:{content_format}"
        if action and content_format
        else "back:content_type"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Ввести заново",
                    callback_data="title:retry",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔁 Сменить категорию",
                    callback_data=back_callback,
                ),
            ],
        ],
    )


def rating_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для оценки от 1 до 10 по одной категории."""
    buttons = [
        InlineKeyboardButton(text=str(n), callback_data=f"rate:{n}")
        for n in range(1, 11)
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            buttons[:5],
            buttons[5:],
        ],
    )


def episodes_keyboard(
    total_episodes: int,
    season_number: int,
) -> InlineKeyboardMarkup:
    """Клавиатура для выбора количества просмотренных серий в сезоне."""
    buttons: list[list[InlineKeyboardButton]] = []
    for i in range(0, total_episodes, 5):
        row = [
            InlineKeyboardButton(
                text=str(n),
                callback_data=f"ep:{season_number}:{n}",
            )
            for n in range(i + 1, min(i + 6, total_episodes + 1))
        ]
        buttons.append(row)
    buttons.append([
        InlineKeyboardButton(text="0", callback_data=f"ep:{season_number}:0"),
    ])
    buttons.append([
        InlineKeyboardButton(text="✅ Готово", callback_data="ep:done"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def season_list_keyboard(
    seasons: list[dict],
    watched: dict[int, int],
) -> InlineKeyboardMarkup:
    """Клавиатура со списком сезонов для выбора."""
    buttons: list[list[InlineKeyboardButton]] = []
    for s in seasons:
        num = s["season_number"]
        name = s["name"]
        ep_count = s["episode_count"]
        done = watched.get(num, 0)
        text = f"{name}: {done}/{ep_count}"
        buttons.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"season:{num}",
            ),
        ])
    buttons.append([
        InlineKeyboardButton(text="✅ Завершить трекинг", callback_data="season:done"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


__all__ = (
    "content_type_keyboard",
    "episodes_keyboard",
    "format_keyboard",
    "main_menu_keyboard",
    "rating_keyboard",
    "season_list_keyboard",
    "selected_type_keyboard",
    "tmdb_guess_keyboard",
    "tmdb_retry_keyboard",
)
