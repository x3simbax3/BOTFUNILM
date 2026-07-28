from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.lang import get_locale

text = get_locale().keyboards
EPISODES_PAGE_SIZE = 50


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text.MAIN_LIBRARY, callback_data="menu:library"
                ),
            ],
            [InlineKeyboardButton(text=text.MAIN_ADD, callback_data="menu:add")],
        ],
    )


def library_keyboard(
    filters: dict[str, bool],
    page: int,
    has_more: bool,
    sort_order: str = "recent",
) -> InlineKeyboardMarkup:
    format_unfiltered = filters.get("series", False) and filters.get(
        "full_length", False
    )
    type_unfiltered = all(
        filters.get(name, False) for name in ("movie", "anime", "cartoon")
    )

    def filter_selected(name: str) -> bool:
        if name in {"series", "full_length"}:
            unfiltered = format_unfiltered
        elif name in {"movie", "anime", "cartoon"}:
            unfiltered = type_unfiltered
        else:
            return filters.get(name, False)
        return not unfiltered and filters.get(name, False)

    rows = [
        [
            InlineKeyboardButton(
                text=text.selected(
                    text.FILTER_RECENT,
                    sort_order == "recent",
                ),
                callback_data="library:sort:recent",
            ),
            InlineKeyboardButton(
                text=text.selected(text.SORT_RATING, sort_order == "rating"),
                callback_data="library:sort:rating",
            ),
        ],
        [
            InlineKeyboardButton(
                text=text.selected(text.FILTER_SERIES, filter_selected("series")),
                callback_data="library:filter:series",
            ),
            InlineKeyboardButton(
                text=text.selected(
                    text.FILTER_FULL_LENGTH,
                    filter_selected("full_length"),
                ),
                callback_data="library:filter:full_length",
            ),
        ],
        [
            InlineKeyboardButton(
                text=text.selected(text.FILTER_MOVIES, filter_selected("movie")),
                callback_data="library:filter:movie",
            ),
            InlineKeyboardButton(
                text=text.selected(text.FILTER_ANIME, filter_selected("anime")),
                callback_data="library:filter:anime",
            ),
            InlineKeyboardButton(
                text=text.selected(text.FILTER_CARTOONS, filter_selected("cartoon")),
                callback_data="library:filter:cartoon",
            ),
        ],
        [
            InlineKeyboardButton(
                text=text.selected(
                    text.FILTER_COMPLETED,
                    filter_selected("completed"),
                ),
                callback_data="library:filter:completed",
            ),
            InlineKeyboardButton(
                text=text.selected(
                    text.FILTER_PLANNED,
                    filter_selected("planned"),
                ),
                callback_data="library:filter:planned",
            ),
        ],
        [
            InlineKeyboardButton(
                text=text.RESET_FILTERS,
                callback_data="library:filter:all",
            ),
        ],
    ]

    pagination = []
    if page > 0:
        pagination.append(
            InlineKeyboardButton(
                text=text.PREVIOUS_PAGE,
                callback_data=f"library:page:{page - 1}",
            )
        )
    if has_more:
        pagination.append(
            InlineKeyboardButton(
                text=text.NEXT_PAGE,
                callback_data=f"library:page:{page + 1}",
            )
        )
    if pagination:
        rows.append(pagination)

    rows.append([InlineKeyboardButton(text=text.TO_MENU, callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def library_item_keyboard(*, planned: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if planned:
        rows.append(
            [
                InlineKeyboardButton(
                    text=text.MARK_WATCHED,
                    callback_data="library:item:watched",
                )
            ]
        )
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text=text.EDIT_ITEM,
                    callback_data="library:item:edit",
                ),
                InlineKeyboardButton(
                    text=text.DELETE_ITEM,
                    callback_data="library:item:delete",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=text.TO_LIBRARY,
                    callback_data="library:back",
                )
            ],
        ]
    )
    return InlineKeyboardMarkup(
        inline_keyboard=rows,
    )


def library_edit_keyboard(*, series: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=text.EDIT_RATING,
                callback_data="library:item:edit:rating",
            )
        ]
    ]
    if series:
        rows.append(
            [
                InlineKeyboardButton(
                    text=text.EDIT_PROGRESS,
                    callback_data="library:item:edit:progress",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=text.BACK,
                callback_data="library:item:edit:back",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def library_delete_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text.CONFIRM_DELETE,
                    callback_data="library:item:delete:confirm",
                ),
                InlineKeyboardButton(
                    text=text.CANCEL,
                    callback_data="library:item:delete:cancel",
                ),
            ]
        ]
    )


def format_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text.FORMAT_FULL_LENGTH,
                    callback_data=f"format:{action}:full_length",
                ),
                InlineKeyboardButton(
                    text=text.FORMAT_SERIES,
                    callback_data=f"format:{action}:series",
                ),
            ],
            [InlineKeyboardButton(text=text.BACK, callback_data="back:main")],
        ],
    )


def content_type_keyboard(action: str, content_format: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text.TYPE_MOVIE,
                    callback_data=f"type:{action}:{content_format}:movie",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=text.TYPE_ANIME,
                    callback_data=f"type:{action}:{content_format}:anime",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=text.TYPE_CARTOON,
                    callback_data=f"type:{action}:{content_format}:cartoon",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=text.BACK,
                    callback_data=f"back:format:{action}",
                )
            ],
        ],
    )


def selected_type_keyboard(action: str, content_format: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text.BACK,
                    callback_data=f"back:content_type:{action}:{content_format}",
                ),
            ],
        ],
    )


def tmdb_guess_keyboard(
    position: int = 0,
    total: int = 1,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if total > 1:
        rows.append(
            [
                InlineKeyboardButton(text="《", callback_data="tmdb_guess:previous"),
                InlineKeyboardButton(
                    text=f"{position + 1} / {total}",
                    callback_data="tmdb_guess:position",
                ),
                InlineKeyboardButton(text="》", callback_data="tmdb_guess:next"),
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=text.GUESS_YES,
                callback_data="tmdb_guess:yes",
            ),
            InlineKeyboardButton(text=text.GUESS_NO, callback_data="tmdb_guess:no"),
        ]
    )
    return InlineKeyboardMarkup(
        inline_keyboard=rows,
    )


def watch_status_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text.STATUS_COMPLETED,
                    callback_data="watch_status:completed",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=text.STATUS_PLANNED,
                    callback_data="watch_status:planned",
                ),
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
                    text=text.ANOTHER_TITLE,
                    callback_data="title:retry",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=text.ANOTHER_CATEGORY,
                    callback_data=back_callback,
                ),
            ],
        ],
    )


def rating_keyboard() -> InlineKeyboardMarkup:
    """Build a keyboard for rating one category from 1 to 10."""
    buttons = [
        InlineKeyboardButton(text=str(n), callback_data=f"rate:{n}")
        for n in range(1, 11)
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            buttons[:5],
            buttons[5:],
            [InlineKeyboardButton(text=text.BACK, callback_data="rating:back")],
        ],
    )


def episodes_keyboard(
    total_episodes: int,
    season_number: int,
    page: int = 0,
) -> InlineKeyboardMarkup:
    """Build a keyboard for selecting watched episodes in a season."""
    total_pages = max(
        1, (total_episodes + EPISODES_PAGE_SIZE - 1) // EPISODES_PAGE_SIZE
    )
    if not 0 <= page < total_pages:
        raise ValueError("Invalid episode page")

    buttons: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=text.ALL_EPISODES,
                callback_data=f"ep:{season_number}:{total_episodes}",
            )
        ]
    ]
    first_episode = page * EPISODES_PAGE_SIZE + 1
    last_episode = min(total_episodes, first_episode + EPISODES_PAGE_SIZE - 1)
    for i in range(first_episode, last_episode + 1, 5):
        row = [
            InlineKeyboardButton(
                text=str(n),
                callback_data=f"ep:{season_number}:{n}",
            )
            for n in range(i, min(i + 5, last_episode + 1))
        ]
        buttons.append(row)
    if total_pages > 1:
        previous_page = max(0, page - 1)
        next_page = min(total_pages - 1, page + 1)
        buttons.append(
            [
                InlineKeyboardButton(
                    text="‹",
                    callback_data=(
                        f"ep:page:{previous_page}" if page > 0 else "ep:noop"
                    ),
                ),
                InlineKeyboardButton(
                    text=f"{page + 1}/{total_pages}",
                    callback_data="ep:noop",
                ),
                InlineKeyboardButton(
                    text="›",
                    callback_data=(
                        f"ep:page:{next_page}" if page < total_pages - 1 else "ep:noop"
                    ),
                ),
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(text=text.BACK, callback_data="ep:back"),
            InlineKeyboardButton(text=text.SAVE, callback_data="ep:done"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def season_list_keyboard(
    seasons: list[dict],
    watched: dict[int, int],
) -> InlineKeyboardMarkup:
    """Build a keyboard containing seasons and their progress."""
    buttons: list[list[InlineKeyboardButton]] = []
    buttons.append(
        [
            InlineKeyboardButton(
                text=text.ALL_SEASONS,
                callback_data="season:all",
            )
        ]
    )
    for s in seasons:
        num = s["season_number"]
        name = s["name"]
        ep_count = s["episode_count"]
        done = watched.get(num, 0)
        button_text = text.season_progress(name, done, ep_count)
        buttons.append(
            [
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"season:{num}",
                ),
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(text=text.SAVE_PROGRESS, callback_data="season:done"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


__all__ = (
    "EPISODES_PAGE_SIZE",
    "content_type_keyboard",
    "episodes_keyboard",
    "format_keyboard",
    "library_delete_keyboard",
    "library_edit_keyboard",
    "library_item_keyboard",
    "library_keyboard",
    "main_menu_keyboard",
    "rating_keyboard",
    "season_list_keyboard",
    "selected_type_keyboard",
    "tmdb_guess_keyboard",
    "tmdb_retry_keyboard",
    "watch_status_keyboard",
)
