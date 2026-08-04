"""Read-only aggregate queries for the Telegram admin overview."""

from __future__ import annotations

from dataclasses import dataclass

from src.database.connection import connection_scope

ADMIN_USERS_PAGE_SIZE = 10


@dataclass(frozen=True)
class AdminOverview:
    total_users: int
    active_users: int
    inactive_users: int
    new_24h: int
    new_7d: int
    new_30d: int
    active_24h: int
    active_7d: int
    active_30d: int
    activated_users: int
    library_items: int
    rated_items: int
    tracked_series: int
    news_users: int
    generated_at: str

    @property
    def activation_percent(self) -> float:
        if not self.total_users:
            return 0.0
        return self.activated_users * 100 / self.total_users

    @property
    def average_library_items(self) -> float:
        if not self.total_users:
            return 0.0
        return self.library_items / self.total_users


@dataclass(frozen=True)
class AdminUserSummary:
    user_id: int
    username: str | None
    display_name: str | None
    is_active: int
    started_at: str
    last_activity_at: str
    library_items: int


@dataclass(frozen=True)
class AdminUserPage:
    users: tuple[AdminUserSummary, ...]
    page: int
    total_pages: int
    total_users: int


@dataclass(frozen=True)
class AdminUserDetails:
    user_id: int
    username: str | None
    display_name: str | None
    is_active: int
    news_enabled: int
    started_at: str
    last_started_at: str
    last_activity_at: str
    library_items: int
    planned_items: int
    watching_items: int
    completed_items: int
    on_hold_items: int
    dropped_items: int
    rated_items: int
    average_rating: float | None
    tracked_series: int


@dataclass(frozen=True)
class AdminActivityDay:
    event_date: str
    active_users: int
    new_users: int
    returning_users: int


@dataclass(frozen=True)
class AdminActivity:
    days: int
    dau: int
    wau: int
    mau: int
    new_users: int
    returning_users: int
    searches: int
    library_opens: int
    media_added: int
    ratings_set: int
    progress_updates: int
    daily: tuple[AdminActivityDay, ...]
    generated_at: str


async def get_admin_overview(
    *,
    database_url: str | None = None,
) -> AdminOverview:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT
                COUNT(*) AS total_users,
                COUNT(*) FILTER (WHERE is_active = 1) AS active_users,
                COUNT(*) FILTER (WHERE is_active = 0) AS inactive_users,
                COUNT(*) FILTER (
                    WHERE started_at >= datetime('now', '-1 day')
                ) AS new_24h,
                COUNT(*) FILTER (
                    WHERE started_at >= datetime('now', '-7 days')
                ) AS new_7d,
                COUNT(*) FILTER (
                    WHERE started_at >= datetime('now', '-30 days')
                ) AS new_30d,
                COUNT(*) FILTER (
                    WHERE last_activity_at >= datetime('now', '-1 day')
                ) AS active_24h,
                COUNT(*) FILTER (
                    WHERE last_activity_at >= datetime('now', '-7 days')
                ) AS active_7d,
                COUNT(*) FILTER (
                    WHERE last_activity_at >= datetime('now', '-30 days')
                ) AS active_30d,
                COUNT(*) FILTER (
                    WHERE EXISTS (
                        SELECT 1 FROM user_media
                        WHERE user_media.user_id = bot_users.user_id
                    )
                ) AS activated_users,
                (SELECT COUNT(*) FROM user_media) AS library_items,
                (SELECT COUNT(*) FROM user_media WHERE user_rating IS NOT NULL)
                    AS rated_items,
                (SELECT COUNT(*) FROM user_media WHERE is_tracking = 1)
                    AS tracked_series,
                COUNT(*) FILTER (
                    WHERE is_active = 1 AND news_enabled = 1
                ) AS news_users,
                CURRENT_TIMESTAMP AS generated_at
            FROM bot_users
            """
        ) as cursor:
            row = await cursor.fetchone()

    return AdminOverview(**dict(row))


async def get_admin_users(
    page: int,
    *,
    page_size: int = ADMIN_USERS_PAGE_SIZE,
    database_url: str | None = None,
) -> AdminUserPage:
    if page <= 0:
        raise ValueError("page must be positive")
    if page_size <= 0:
        raise ValueError("page_size must be positive")

    async with connection_scope(database_url) as connection:
        async with connection.execute("SELECT COUNT(*) FROM bot_users") as cursor:
            total_users = int((await cursor.fetchone())[0])

        total_pages = max(1, (total_users + page_size - 1) // page_size)
        current_page = min(page, total_pages)
        async with connection.execute(
            """
            SELECT
                bot_users.user_id,
                bot_users.username,
                bot_users.display_name,
                bot_users.is_active,
                bot_users.started_at,
                bot_users.last_activity_at,
                COUNT(user_media.media_id) AS library_items
            FROM bot_users
            LEFT JOIN user_media ON user_media.user_id = bot_users.user_id
            GROUP BY bot_users.user_id
            ORDER BY bot_users.last_activity_at DESC, bot_users.user_id
            LIMIT ? OFFSET ?
            """,
            (page_size, (current_page - 1) * page_size),
        ) as cursor:
            users = tuple(
                AdminUserSummary(**dict(row)) for row in await cursor.fetchall()
            )

    return AdminUserPage(
        users=users,
        page=current_page,
        total_pages=total_pages,
        total_users=total_users,
    )


async def get_admin_user(
    user_id: int,
    *,
    database_url: str | None = None,
) -> AdminUserDetails | None:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT
                bot_users.user_id,
                bot_users.username,
                bot_users.display_name,
                bot_users.is_active,
                bot_users.news_enabled,
                bot_users.started_at,
                bot_users.last_started_at,
                bot_users.last_activity_at,
                COUNT(user_media.media_id) AS library_items,
                COUNT(*) FILTER (WHERE user_media.status = 'planned')
                    AS planned_items,
                COUNT(*) FILTER (WHERE user_media.status = 'watching')
                    AS watching_items,
                COUNT(*) FILTER (WHERE user_media.status = 'completed')
                    AS completed_items,
                COUNT(*) FILTER (WHERE user_media.status = 'on_hold')
                    AS on_hold_items,
                COUNT(*) FILTER (WHERE user_media.status = 'dropped')
                    AS dropped_items,
                COUNT(*) FILTER (WHERE user_media.user_rating IS NOT NULL)
                    AS rated_items,
                AVG(user_media.user_rating) AS average_rating,
                COUNT(*) FILTER (WHERE user_media.is_tracking = 1)
                    AS tracked_series
            FROM bot_users
            LEFT JOIN user_media ON user_media.user_id = bot_users.user_id
            WHERE bot_users.user_id = ?
            GROUP BY bot_users.user_id
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()

    return None if row is None else AdminUserDetails(**dict(row))


async def get_admin_activity(
    days: int,
    *,
    database_url: str | None = None,
) -> AdminActivity:
    if days not in {7, 30}:
        raise ValueError("days must be 7 or 30")
    start_modifier = f"-{days - 1} days"

    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT
                (
                    SELECT COUNT(DISTINCT user_id)
                    FROM bot_user_daily_events
                    WHERE event_type = 'active'
                      AND event_date = date('now')
                ) AS dau,
                (
                    SELECT COUNT(DISTINCT user_id)
                    FROM bot_user_daily_events
                    WHERE event_type = 'active'
                      AND event_date >= date('now', '-6 days')
                ) AS wau,
                (
                    SELECT COUNT(DISTINCT user_id)
                    FROM bot_user_daily_events
                    WHERE event_type = 'active'
                      AND event_date >= date('now', '-29 days')
                ) AS mau,
                (
                    SELECT COUNT(*) FROM bot_users
                    WHERE date(started_at) >= date('now', ?)
                ) AS new_users,
                (
                    SELECT COUNT(DISTINCT events.user_id)
                    FROM bot_user_daily_events AS events
                    JOIN bot_users ON bot_users.user_id = events.user_id
                    WHERE events.event_type = 'active'
                      AND events.event_date >= date('now', ?)
                      AND date(bot_users.started_at) < events.event_date
                ) AS returning_users,
                COALESCE(SUM(event_count) FILTER (
                    WHERE event_type = 'search'
                ), 0) AS searches,
                COALESCE(SUM(event_count) FILTER (
                    WHERE event_type = 'library_open'
                ), 0) AS library_opens,
                COALESCE(SUM(event_count) FILTER (
                    WHERE event_type = 'media_added'
                ), 0) AS media_added,
                COALESCE(SUM(event_count) FILTER (
                    WHERE event_type = 'rating_set'
                ), 0) AS ratings_set,
                COALESCE(SUM(event_count) FILTER (
                    WHERE event_type = 'progress_updated'
                ), 0) AS progress_updates,
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
                SELECT date(event_date, '+1 day')
                FROM dates
                WHERE event_date < date('now')
            )
            SELECT
                dates.event_date,
                COUNT(DISTINCT events.user_id) AS active_users,
                (
                    SELECT COUNT(*) FROM bot_users
                    WHERE date(started_at) = dates.event_date
                ) AS new_users,
                COUNT(DISTINCT CASE
                    WHEN date(bot_users.started_at) < dates.event_date
                    THEN events.user_id
                END) AS returning_users
            FROM dates
            LEFT JOIN bot_user_daily_events AS events
                ON events.event_date = dates.event_date
               AND events.event_type = 'active'
            LEFT JOIN bot_users ON bot_users.user_id = events.user_id
            GROUP BY dates.event_date
            ORDER BY dates.event_date
            """,
            (start_modifier,),
        ) as cursor:
            daily = tuple(
                AdminActivityDay(**dict(row)) for row in await cursor.fetchall()
            )

    return AdminActivity(days=days, daily=daily, **totals)


__all__ = (
    "ADMIN_USERS_PAGE_SIZE",
    "AdminActivity",
    "AdminActivityDay",
    "AdminOverview",
    "AdminUserDetails",
    "AdminUserPage",
    "AdminUserSummary",
    "get_admin_overview",
    "get_admin_activity",
    "get_admin_user",
    "get_admin_users",
)
