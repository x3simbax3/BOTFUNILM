from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.lang import get_locale

text = get_locale().keyboards


def library_keyboard(
    filters: dict[str, bool],
    page: int,
    has_more: bool,
    sort_order: str = "recent",
    filter_group: str | None = None,
) -> InlineKeyboardMarkup:
    if filter_group is not None:
        return _library_filter_group_keyboard(filters, sort_order, filter_group)

    rows = [
        [
            InlineKeyboardButton(
                text=text.RESET_FILTERS,
                callback_data="library:filter:all",
            )
        ],
        [
            InlineKeyboardButton(
                text=text.FILTER_FORMAT_GROUP,
                callback_data="library:filters:format",
            ),
            InlineKeyboardButton(
                text=_compact_filter_value(
                    filters,
                    ("full_length", "series"),
                    ("Полный метр", "Сериал"),
                ),
                callback_data="library:filters:format",
            ),
        ],
        [
            InlineKeyboardButton(
                text=text.FILTER_CATEGORY_GROUP,
                callback_data="library:filters:category",
            ),
            InlineKeyboardButton(
                text=_compact_filter_value(
                    filters,
                    ("movie", "anime", "cartoon"),
                    ("Кино", "Аниме", "Мульт"),
                ),
                callback_data="library:filters:category",
            ),
        ],
        [
            InlineKeyboardButton(
                text=text.FILTER_STATUS_GROUP,
                callback_data="library:filters:status",
            ),
            InlineKeyboardButton(
                text=_compact_filter_value(
                    filters,
                    ("completed", "planned", "unfinished", "ongoing"),
                    ("Готово", "Хочу", "Не досм.", "Выходит"),
                ),
                callback_data="library:filters:status",
            ),
        ],
        [
            InlineKeyboardButton(
                text=text.FILTER_SORT_GROUP,
                callback_data="library:filters:sort",
            ),
            InlineKeyboardButton(
                text={
                    "recent": "Дата",
                    "rating": "Моя оценка",
                    "tmdb_rating": "Оценка TMDB",
                    "title": "Название",
                }.get(sort_order, "Дата"),
                callback_data="library:filters:sort",
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


def _compact_filter_value(
    filters: dict[str, bool],
    names: tuple[str, ...],
    labels: tuple[str, ...],
) -> str:
    selected = [
        label for name, label in zip(names, labels, strict=True) if filters.get(name)
    ]
    if len(selected) == len(names):
        return "Все"
    if len(selected) == 1:
        return selected[0]
    if not selected:
        return "Нет"
    return str(len(selected))


def _library_filter_group_keyboard(
    filters: dict[str, bool],
    sort_order: str,
    group: str,
) -> InlineKeyboardMarkup:
    definitions = {
        "format": (
            "format_all",
            (("full_length", text.FILTER_FULL_LENGTH), ("series", text.FILTER_SERIES)),
        ),
        "category": (
            "category_all",
            (
                ("movie", text.FILTER_MOVIES),
                ("anime", text.FILTER_ANIME),
                ("cartoon", text.FILTER_CARTOONS),
            ),
        ),
        "status": (
            "status_all",
            (
                ("completed", text.FILTER_COMPLETED),
                ("planned", text.FILTER_PLANNED),
                ("unfinished", text.FILTER_UNFINISHED),
                ("ongoing", text.FILTER_ONGOING),
            ),
        ),
    }
    if group == "sort":
        options = (
            ("recent", text.FILTER_RECENT),
            ("rating", text.SORT_RATING),
            ("tmdb_rating", text.SORT_TMDB_RATING),
            ("title", text.SORT_TITLE),
        )
        rows = [
            [
                InlineKeyboardButton(
                    text=text.selected(label, sort_order == value),
                    callback_data=f"library:sort:{value}",
                )
            ]
            for value, label in options
        ]
    else:
        reset_name, options = definitions[group]
        all_selected = all(filters.get(name, False) for name, _ in options)
        rows = [
            [
                InlineKeyboardButton(
                    text=text.selected(text.FILTER_ALL, all_selected),
                    callback_data=f"library:filter:{reset_name}",
                )
            ]
        ]
        rows.extend(
            [
                InlineKeyboardButton(
                    text=text.selected(
                        label,
                        not all_selected and filters.get(name, False),
                    ),
                    callback_data=f"library:filter:{name}",
                )
            ]
            for name, label in options
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=text.FILTERS_BACK,
                callback_data="library:filters:back",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def library_item_keyboard(
    *,
    planned: bool = False,
    released: bool = True,
    tracking_available: bool = False,
    tracking_enabled: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if planned and released:
        rows.append(
            [
                InlineKeyboardButton(
                    text=text.MARK_WATCHED,
                    callback_data="library:item:watched",
                )
            ]
        )
    if tracking_available:
        rows.append(
            [
                InlineKeyboardButton(
                    text=(
                        text.TRACKING_DISABLE
                        if tracking_enabled
                        else text.TRACKING_ENABLE
                    ),
                    callback_data="series:tracking:toggle",
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


def library_edit_keyboard(
    *,
    series: bool,
    released: bool = True,
) -> InlineKeyboardMarkup:
    rows = []
    if released:
        rows.append(
            [
                InlineKeyboardButton(
                    text=text.EDIT_RATING,
                    callback_data="library:item:edit:rating",
                )
            ]
        )
    if series and released:
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
