"""Admin queries for user activity."""

from __future__ import annotations

from src.database.admin.models import AdminActivity, AdminActivityDay
from src.database.connection import connection_scope


async def get_admin_activity(
    days: int, *, database_url: str | None = None
) -> AdminActivity:
    if days not in {7, 30}:
        raise ValueError("days must be 7 or 30")
    start_modifier = f"-{days - 1} days"

    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT
                (SELECT COUNT(DISTINCT user_id) FROM bot_user_daily_events
                 WHERE event_type = 'active' AND event_date = date('now')) AS dau,
                (SELECT COUNT(DISTINCT user_id) FROM bot_user_daily_events
                 WHERE event_type = 'active' AND event_date >= date('now', '-6 days')) AS wau,
                (SELECT COUNT(DISTINCT user_id) FROM bot_user_daily_events
                 WHERE event_type = 'active' AND event_date >= date('now', '-29 days')) AS mau,
                (SELECT COUNT(*) FROM bot_users
                 WHERE date(started_at) >= date('now', ?)) AS new_users,
                (SELECT COUNT(DISTINCT events.user_id)
                 FROM bot_user_daily_events AS events
                 JOIN bot_users ON bot_users.user_id = events.user_id
                 WHERE events.event_type = 'active'
                   AND events.event_date >= date('now', ?)
                   AND date(bot_users.started_at) < events.event_date) AS returning_users,
                COALESCE(SUM(event_count) FILTER (WHERE event_type = 'search'), 0) AS searches,
                COALESCE(SUM(event_count) FILTER (WHERE event_type = 'library_open'), 0) AS library_opens,
                COALESCE(SUM(event_count) FILTER (WHERE event_type = 'media_added'), 0) AS media_added,
                COALESCE(SUM(event_count) FILTER (WHERE event_type = 'rating_set'), 0) AS ratings_set,
                COALESCE(SUM(event_count) FILTER (WHERE event_type = 'progress_updated'), 0) AS progress_updates,
                CURRENT_TIMESTAMP AS generated_at
            FROM bot_user_daily_events
            WHERE event_date >= date('now', ?)
            """,
            (start_modifier, start_modifier, start_modifier),
        ) as cursor:
            totals = dict(await cursor.fetchone())
        async with connection.execute(
            """
            WITH RECURSIVE dates(event_date) AS (
                SELECT date('now', ?)
                UNION ALL
                SELECT date(event_date, '+1 day') FROM dates
                WHERE event_date < date('now')
            )
            SELECT dates.event_date, COUNT(DISTINCT events.user_id) AS active_users,
                   (SELECT COUNT(*) FROM bot_users
                    WHERE date(started_at) = dates.event_date) AS new_users,
                   COUNT(DISTINCT CASE WHEN date(bot_users.started_at) < dates.event_date
                     THEN events.user_id END) AS returning_users
            FROM dates
            LEFT JOIN bot_user_daily_events AS events
              ON events.event_date = dates.event_date AND events.event_type = 'active'
            LEFT JOIN bot_users ON bot_users.user_id = events.user_id
            GROUP BY dates.event_date
            ORDER BY dates.event_date
            """,
            (start_modifier,),
        ) as cursor:
            daily = tuple(AdminActivityDay(**dict(row)) for row in await cursor.fetchall())
    return AdminActivity(days=days, daily=daily, **totals)
