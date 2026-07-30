from datetime import date
from html import escape

from .tracking import tracking_status_line

DETAILS_LOAD_FAILED = "Не удалось получить информацию о сериале. Попробуй позже."
PROGRESS_LOAD_FAILED = "Не удалось загрузить сохранённый прогресс. Попробуй позже."
SAVED_PROGRESS_INVALID = "Сохранённый прогресс сериала некорректен. Попробуй позже."
INVALID_SEASON = "Некорректный сезон"
SEASON_NOT_FOUND = "Сезон не найден"
SEASON_NOT_AVAILABLE = "В этом сезоне пока нет вышедших серий"
INVALID_EPISODE = "Некорректный эпизод"
INVALID_PROGRESS_TRANSITION = "Некорректный переход прогресса"
INVALID_PROGRESS = "Некорректный прогресс сериала. Выбери эпизоды заново."
PROGRESS_SAVE_FAILED = "Не удалось сохранить прогресс. Попробуй ещё раз."
NO_EPISODES_SELECTED = "Отметь хотя бы одну просмотренную серию"


def default_season_name(season_number: int) -> str:
    return f"Сезон {season_number}"


def series_tracking_text(
    title: str,
    seasons: list[dict],
    *,
    is_ongoing: bool = False,
) -> str:
    available = sum(season["episode_count"] for season in seasons)
    announced = sum(
        season.get("announced_episode_count", season["episode_count"])
        for season in seasons
    )
    lines = [
        f"━━━  <b>{escape(title)}</b>  ━━━",
        f"<i>{len(seasons)} сез. · вышло {available} из {announced} сер.</i>",
        "",
    ]
    if is_ongoing:
        lines.extend(["🔴 <b>Сейчас выходит</b>", ""])
    lines.append("<b>Прогресс по сезонам</b>")
    for season in seasons:
        season_available = season["episode_count"]
        season_announced = season.get("announced_episode_count", season_available)
        lines.append(
            f"{escape(season['name'])} · вышло "
            f"{season_available} из {season_announced} сер."
        )
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
        f"━━━  <b>{escape(title)}</b>  ━━━\n"
        f"<i>{escape(season_name)}</i>\n\n"
        f"Просмотрено · <b>{already_watched} из {total_episodes}</b>\n"
        f"Осталось · <b>{remaining}</b>\n\n"
        "<b>Сколько серий просмотрено?</b>"
    )


def tracking_complete_text(
    title: str,
    total_episodes: int,
    watched_episodes: int,
    average: float | None,
    *,
    is_ongoing: bool = False,
    announced_episodes: int | None = None,
    tracking_enabled: bool | None = None,
) -> str:
    remaining = _remaining_episodes(total_episodes, watched_episodes)
    if is_ongoing and remaining == 0:
        status = "Все вышедшие серии просмотрены"
    else:
        status = "Завершён" if remaining == 0 else f"В процессе · осталось {remaining}"
    total_text = (
        f"{total_episodes} вышло из {announced_episodes}"
        if announced_episodes is not None and announced_episodes != total_episodes
        else str(total_episodes)
    )
    rating_line = (
        f"Моя оценка · <b>{average:.1f}/10</b>\n" if average is not None else ""
    )
    result = (
        "✓ <b>Прогресс сохранён</b>\n\n"
        f"▣\u00a0<b>{escape(title)}</b>\n"
        f"Просмотрено · <b>{watched_episodes} из {total_text}</b>\n"
        f"Статус · <b>{status}</b>\n"
        f"{rating_line}"
    )
    if tracking_enabled is not None:
        result += f"{tracking_status_line(tracking_enabled)}\n"
    return f"{result}<i>{date.today().strftime('%d.%m.%Y')}</i>"


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
    "SEASON_NOT_AVAILABLE",
    "default_season_name",
    "episodes_prompt_text",
    "series_tracking_text",
    "tracking_complete_text",
)
