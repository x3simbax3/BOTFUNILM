from datetime import date
from html import escape

DETAILS_LOAD_FAILED = "Не удалось получить информацию о сериале. Попробуй позже."
PROGRESS_LOAD_FAILED = "Не удалось загрузить сохранённый прогресс. Попробуй позже."
SAVED_PROGRESS_INVALID = "Сохранённый прогресс сериала некорректен. Попробуй позже."
INVALID_SEASON = "Некорректный сезон"
SEASON_NOT_FOUND = "Сезон не найден"
INVALID_EPISODE = "Некорректный эпизод"
INVALID_PROGRESS_TRANSITION = "Некорректный переход прогресса"
INVALID_PROGRESS = "Некорректный прогресс сериала. Выбери эпизоды заново."
PROGRESS_SAVE_FAILED = "Не удалось сохранить прогресс. Попробуй ещё раз."
NO_EPISODES_SELECTED = "Отметь хотя бы одну просмотренную серию"


def default_season_name(season_number: int) -> str:
    return f"Сезон {season_number}"


def series_tracking_text(title: str, seasons: list[dict]) -> str:
    total = sum(season["episode_count"] for season in seasons)
    lines = [
        f"📺 <b>{escape(title)}</b>",
        f"<i>{len(seasons)} сез. · {total} сер.</i>",
        "",
        "<b>Прогресс по сезонам</b>",
    ]
    for season in seasons:
        lines.append(f"{escape(season['name'])} · {season['episode_count']} сер.")
    lines.append("\nВыбери сезон")
    return "\n".join(lines)


def episodes_prompt_text(
    title: str,
    season_name: str,
    total_episodes: int,
    already_watched: int,
) -> str:
    remaining = _remaining_episodes(total_episodes, already_watched)
    return (
        f"📺 <b>{escape(title)}</b>\n"
        f"<i>{escape(season_name)}</i>\n\n"
        f"Просмотрено · <b>{already_watched} из {total_episodes}</b>\n"
        f"Осталось · <b>{remaining}</b>\n\n"
        "<b>Сколько серий просмотрено?</b>"
    )


def tracking_complete_text(
    title: str,
    total_episodes: int,
    watched_episodes: int,
    average: float,
) -> str:
    remaining = _remaining_episodes(total_episodes, watched_episodes)
    status = "Завершён" if remaining == 0 else f"В процессе · осталось {remaining}"
    return (
        "✓ <b>Прогресс сохранён</b>\n\n"
        f"📺 <b>{escape(title)}</b>\n"
        f"Просмотрено · <b>{watched_episodes} из {total_episodes}</b>\n"
        f"Статус · <b>{status}</b>\n"
        f"Моя оценка · <b>{average:.1f}/10</b>\n"
        f"<i>{date.today().strftime('%d.%m.%Y')}</i>"
    )


def _remaining_episodes(total_episodes: int, watched_episodes: int) -> int:
    if (
        type(total_episodes) is not int
        or type(watched_episodes) is not int
        or total_episodes < 0
        or not 0 <= watched_episodes <= total_episodes
    ):
        raise ValueError("Episode progress must stay between zero and the total")
    return total_episodes - watched_episodes


__all__ = (
    "DETAILS_LOAD_FAILED",
    "INVALID_EPISODE",
    "INVALID_PROGRESS",
    "INVALID_PROGRESS_TRANSITION",
    "INVALID_SEASON",
    "NO_EPISODES_SELECTED",
    "PROGRESS_LOAD_FAILED",
    "PROGRESS_SAVE_FAILED",
    "SAVED_PROGRESS_INVALID",
    "SEASON_NOT_FOUND",
    "default_season_name",
    "episodes_prompt_text",
    "series_tracking_text",
    "tracking_complete_text",
)
