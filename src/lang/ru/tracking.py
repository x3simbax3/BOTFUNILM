from html import escape

from src.database.media_release_notifications import MediaReleaseNotification
from src.database.series_subscriptions import NotificationItem

from .rating import media_badge_emoji

TRACKED_HEADING = "╭ <b>Отслеживаемые</b>"
TRACKED_EMPTY = (
    "╭ <b>Отслеживаемые</b>\n"
    "╰ <i>Список пуст</i>\n\n"
    "Добавь будущий фильм в «Хочу посмотреть» или включи отслеживание сериала."
)
TRACKED_OPEN_FAILED = "Не удалось открыть отслеживаемые тайтлы."
TRACKING_ENABLED = "Отслеживание активно."
TRACKING_DISABLED = "Отслеживание не активно."
TRACKING_UNAVAILABLE = "Этот сериал уже не выходит."
TRACKING_LIMIT_REACHED = "Можно отслеживать не больше 50 сериалов."
TRACKING_SAVE_FAILED = "Не удалось изменить отслеживание. Попробуй ещё раз."
NOTIFICATION_NOT_FOUND = "Это уведомление больше недоступно."


def tracking_status_line(enabled: bool) -> str:
    status = "Активно" if enabled else "Не активно"
    return f"Отслеживание · <b>{status}</b>"


def replace_tracking_status(text: str, enabled: bool) -> str:
    for current in (False, True):
        text = text.replace(
            tracking_status_line(current), tracking_status_line(enabled)
        )
    return text


def tracked_series_text(items: list, bot_username: str, offset: int = 0) -> str:
    if not items:
        return TRACKED_EMPTY
    lines = [TRACKED_HEADING, "╰ <i>Новые серии и премьеры — в одном месте</i>", ""]
    for index, item in enumerate(items, start=offset + 1):
        url = f"https://t.me/{bot_username}?start=media_{int(item['id'])}"
        badge = media_badge_emoji(dict(item).get("badge"))
        badge_suffix = f" {badge}" if badge else ""
        lines.append(
            f'<a href="{url}">{index}. {escape(item["title"])}</a>{badge_suffix}'
        )
        if item["content_format"] == "series":
            watched = int(item["episodes_watched"] or 0)
            available = int(item["available_episode_count"] or 0)
            lines.append(f"Просмотрено · {watched} из {available} вышедших серий")
        else:
            release_date = item["release_date"] or "дата уточняется"
            lines.append(f"Премьера · {escape(release_date)}")
        if index < offset + len(items):
            lines.append("")
    return "\n".join(lines)


def release_notification_text(
    items: list[NotificationItem],
    page: int,
    total_pages: int,
) -> str:
    lines = ["🔔 <b>Новые серии</b>", ""]
    for item in items:
        count = item.released_count
        word = _episode_word(count)
        lines.append(f"• <b>{escape(item.title)}</b> — вышло {count} {word}")
        if item.season_number is not None and item.episode_number is not None:
            lines.append(
                f"  Последняя · {item.season_number} сезон, {item.episode_number} серия"
            )
    if total_pages > 1:
        lines.extend(["", f"Страница {page + 1} из {total_pages}"])
    return "\n".join(lines)


def media_release_notification_text(
    items: list[MediaReleaseNotification],
) -> str:
    lines = ["🎬 <b>Можно смотреть</b>", ""]
    for item in items:
        lines.append(f"• <b>{escape(item.title)}</b> — тайтл вышел")
    lines.extend(["", "Теперь просмотр можно отметить в библиотеке."])
    return "\n".join(lines)


def _episode_word(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "серия"
    if count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
        return "серии"
    return "серий"


__all__ = (
    "NOTIFICATION_NOT_FOUND",
    "TRACKED_OPEN_FAILED",
    "TRACKING_DISABLED",
    "TRACKING_ENABLED",
    "TRACKING_LIMIT_REACHED",
    "TRACKING_SAVE_FAILED",
    "TRACKING_UNAVAILABLE",
    "release_notification_text",
    "media_release_notification_text",
    "replace_tracking_status",
    "tracking_status_line",
    "tracked_series_text",
)
