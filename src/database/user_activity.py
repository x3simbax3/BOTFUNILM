"""Daily counters used by the admin activity dashboard."""

from __future__ import annotations

from src.database.connection import connection_scope

ACTIVITY_EVENT = "active"
TRACKED_EVENT_TYPES = frozenset(
    {
        "search",
        "library_open",
        "media_added",
        "rating_set",
        "progress_updated",
    }
)


async def record_user_event(
    user_id: int,
    event_type: str,
    *,
    database_url: str | None = None,
) -> None:
    if event_type not in TRACKED_EVENT_TYPES:
        raise ValueError("Unknown user activity event")
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            INSERT INTO bot_user_daily_events (
                user_id, event_date, event_type, event_count
            ) VALUES (?, date('now'), ?, 1)
            ON CONFLICT(user_id, event_date, event_type) DO UPDATE SET
                event_count = event_count + 1
            """,
            (user_id, event_type),
        )


__all__ = (
    "ACTIVITY_EVENT",
    "TRACKED_EVENT_TYPES",
    "record_user_event",
)
