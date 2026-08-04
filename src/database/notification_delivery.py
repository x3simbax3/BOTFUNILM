"""Persistence for aggregate Telegram notification delivery results."""

from __future__ import annotations

from src.database.connection import connection_scope

NOTIFICATION_TYPES = frozenset({"news", "release"})


async def record_notification_delivery(
    notification_type: str,
    *,
    selected: int,
    sent: int,
    failed: int,
    deactivated: int = 0,
    database_url: str | None = None,
) -> None:
    if notification_type not in NOTIFICATION_TYPES:
        raise ValueError("Unknown notification type")
    values = (selected, sent, failed, deactivated)
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("Notification delivery counters must be non-negative integers")
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            INSERT INTO notification_delivery_runs (
                notification_type, selected, sent, failed, deactivated
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (notification_type, *values),
        )


__all__ = ("NOTIFICATION_TYPES", "record_notification_delivery")
