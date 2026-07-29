from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.lang import get_locale

text = get_locale().keyboards
EPISODES_PAGE_SIZE = 50


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
        announced = s.get("announced_episode_count", ep_count)
        if ep_count == 0 and announced > 0:
            button_text = f"{name} · ещё не вышел"
        else:
            button_text = text.season_progress(name, done, ep_count)
        buttons.append(
            [
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"season:{num}" if ep_count > 0 else "ep:noop",
                ),
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(text=text.SAVE_PROGRESS, callback_data="season:done"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)
