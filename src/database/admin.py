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
class AdminExportUser:
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


@dataclass(frozen=True)
class AdminPopularTitle:
    media_id: int
    title: str
    library_users: int


@dataclass(frozen=True)
class AdminLibraries:
    total_items: int
    users_with_library: int
    planned_items: int
    watching_items: int
    completed_items: int
    on_hold_items: int
    dropped_items: int
    full_length_items: int
    series_items: int
    movie_items: int
    anime_items: int
    cartoon_items: int
    rated_items: int
    average_rating: float | None
    tracked_series: int
    popular_movies: tuple[AdminPopularTitle, ...]
    popular_series: tuple[AdminPopularTitle, ...]
    generated_at: str

    @property
    def average_items_per_user(self) -> float:
        if not self.users_with_library:
            return 0.0
        return self.total_items / self.users_with_library


@dataclass(frozen=True)
class AdminNotifications:
    news_subscribers: int
    news_opted_out: int
    series_subscribers: int
    series_subscriptions: int
    pending_series_notifications: int
    sent_series_notifications: int
    pending_release_notifications: int
    sent_release_notifications: int
    news_sent_30d: int
    release_messages_sent_30d: int
    selected_30d: int
    sent_30d: int
    failed_30d: int
    deactivated_30d: int
    blocked_users: int
    last_delivery_at: str | None
    generated_at: str

    @property
    def success_percent_30d(self) -> float:
        if not self.selected_30d:
            return 0.0
        return self.sent_30d * 100 / self.selected_30d


@dataclass(frozen=True)
class AdminSystem:
    catalog_items: int
    tmdb_errors: int
    daily_overdue: int
    weekly_overdue: int
    pending_series_notifications: int
    pending_release_notifications: int
    database_size_bytes: int
    database_free_bytes: int
    database_journal_mode: str
    media_refresh_enabled: int
    notifications_enabled: int
    news_enabled: int
    generated_at: str


ALLOWED_FEATURES = frozenset({"media_refresh", "notifications", "news"})


async def get_admin_system(*, database_url: str | None = None) -> AdminSystem:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT
                COUNT(*) AS catalog_items,
                COUNT(*) FILTER (WHERE tmdb_refresh_error IS NOT NULL)
                    AS tmdb_errors,
                COUNT(*) FILTER (
                    WHERE tmdb_id IS NOT NULL
                      AND (
                        (content_format = 'series' AND (
                            tmdb_in_production = 1 OR tmdb_status IN (
                                'Returning Series', 'Planned', 'In Production'
                            )
                        ))
                        OR (is_released = 0 AND EXISTS (
                            SELECT 1 FROM user_media
                            WHERE user_media.media_id = media.id
                              AND user_media.status = 'planned'
                        ))
                      )
                      AND (
                        tmdb_release_checked_at IS NULL
                        OR tmdb_release_checked_at < datetime('now', '-23 hours')
                      )
                ) AS daily_overdue,
                COUNT(*) FILTER (
                    WHERE tmdb_id IS NOT NULL
                      AND content_format = 'series'
                      AND (
                        tmdb_metadata_checked_at IS NULL
                        OR tmdb_metadata_checked_at
                            < datetime('now', '-6 days 23 hours')
                      )
                ) AS weekly_overdue,
                (SELECT COUNT(*) FROM user_series_notifications AS n
                 LEFT JOIN series_notification_batches AS b ON b.id = n.batch_id
                 WHERE n.batch_id IS NULL OR b.sent_at IS NULL)
                    AS pending_series_notifications,
                (SELECT COUNT(*) FROM user_media_release_notifications
                 WHERE sent_at IS NULL) AS pending_release_notifications,
                CURRENT_TIMESTAMP AS generated_at
            FROM media
            """
        ) as cursor:
            values = dict(await cursor.fetchone())

        pragmas: dict[str, object] = {}
        for pragma in ("page_count", "page_size", "freelist_count", "journal_mode"):
            async with connection.execute(f"PRAGMA {pragma}") as cursor:
                pragmas[pragma] = (await cursor.fetchone())[0]

        async with connection.execute(
            "SELECT feature, enabled FROM bot_features"
        ) as cursor:
            features = {
                row["feature"]: row["enabled"] for row in await cursor.fetchall()
            }

    page_size = int(pragmas["page_size"])
    values.update(
        database_size_bytes=int(pragmas["page_count"]) * page_size,
        database_free_bytes=int(pragmas["freelist_count"]) * page_size,
        database_journal_mode=str(pragmas["journal_mode"]),
        media_refresh_enabled=int(features.get("media_refresh", 1)),
        notifications_enabled=int(features.get("notifications", 1)),
        news_enabled=int(features.get("news", 1)),
    )
    return AdminSystem(**values)


async def is_feature_enabled(feature: str, *, database_url: str | None = None) -> bool:
    if feature not in ALLOWED_FEATURES:
        raise ValueError("Unknown feature")
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            "SELECT enabled FROM bot_features WHERE feature = ?", (feature,)
        ) as cursor:
            row = await cursor.fetchone()
    return bool(row["enabled"]) if row else True


async def toggle_feature(
    feature: str, updated_by: int, *, database_url: str | None = None
) -> bool:
    if feature not in ALLOWED_FEATURES:
        raise ValueError("Unknown feature")
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            INSERT INTO bot_features (feature, enabled, updated_at, updated_by)
            VALUES (?, 0, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(feature) DO UPDATE SET
                enabled = CASE bot_features.enabled WHEN 1 THEN 0 ELSE 1 END,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = excluded.updated_by
            """,
            (feature, updated_by),
        )
        async with connection.execute(
            "SELECT enabled FROM bot_features WHERE feature = ?", (feature,)
        ) as cursor:
            row = await cursor.fetchone()
    return bool(row["enabled"])


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


async def get_admin_libraries(
    *,
    database_url: str | None = None,
) -> AdminLibraries:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT
                COUNT(*) AS total_items,
                COUNT(DISTINCT user_media.user_id) AS users_with_library,
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
                COUNT(*) FILTER (WHERE media.content_format = 'full_length')
                    AS full_length_items,
                COUNT(*) FILTER (WHERE media.content_format = 'series')
                    AS series_items,
                COUNT(*) FILTER (WHERE media.content_type = 'movie')
                    AS movie_items,
                COUNT(*) FILTER (WHERE media.content_type = 'anime')
                    AS anime_items,
                COUNT(*) FILTER (WHERE media.content_type = 'cartoon')
                    AS cartoon_items,
                COUNT(*) FILTER (WHERE user_media.user_rating IS NOT NULL)
                    AS rated_items,
                AVG(user_media.user_rating) AS average_rating,
                COUNT(*) FILTER (WHERE user_media.is_tracking = 1)
                    AS tracked_series,
                CURRENT_TIMESTAMP AS generated_at
            FROM user_media
            JOIN media ON media.id = user_media.media_id
            """
        ) as cursor:
            totals = dict(await cursor.fetchone())

        popular_by_format: dict[str, tuple[AdminPopularTitle, ...]] = {}
        for content_format in ("full_length", "series"):
            async with connection.execute(
                """
                SELECT
                    media.id AS media_id,
                    media.title,
                    COUNT(*) AS library_users
                FROM user_media
                JOIN media ON media.id = user_media.media_id
                WHERE media.content_format = ?
                GROUP BY media.id
                ORDER BY library_users DESC, media.title, media.id
                LIMIT 5
                """,
                (content_format,),
            ) as cursor:
                popular_by_format[content_format] = tuple(
                    AdminPopularTitle(**dict(row)) for row in await cursor.fetchall()
                )

    return AdminLibraries(
        popular_movies=popular_by_format["full_length"],
        popular_series=popular_by_format["series"],
        **totals,
    )


async def get_admin_notifications(
    *,
    database_url: str | None = None,
) -> AdminNotifications:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT
                (
                    SELECT COUNT(*) FROM bot_users
                    WHERE is_active = 1 AND news_enabled = 1
                ) AS news_subscribers,
                (
                    SELECT COUNT(*) FROM bot_users
                    WHERE news_enabled = 0
                ) AS news_opted_out,
                (
                    SELECT COUNT(DISTINCT user_id) FROM user_media
                    WHERE is_tracking = 1
                ) AS series_subscribers,
                (
                    SELECT COUNT(*) FROM user_media
                    WHERE is_tracking = 1
                ) AS series_subscriptions,
                (
                    SELECT COUNT(*)
                    FROM user_series_notifications AS notifications
                    LEFT JOIN series_notification_batches AS batches
                        ON batches.id = notifications.batch_id
                    WHERE notifications.batch_id IS NULL
                       OR batches.sent_at IS NULL
                ) AS pending_series_notifications,
                (
                    SELECT COUNT(*)
                    FROM user_series_notifications AS notifications
                    JOIN series_notification_batches AS batches
                        ON batches.id = notifications.batch_id
                    WHERE batches.sent_at IS NOT NULL
                ) AS sent_series_notifications,
                (
                    SELECT COUNT(*) FROM user_media_release_notifications
                    WHERE sent_at IS NULL
                ) AS pending_release_notifications,
                (
                    SELECT COUNT(*) FROM user_media_release_notifications
                    WHERE sent_at IS NOT NULL
                ) AS sent_release_notifications,
                COALESCE((
                    SELECT SUM(sent) FROM notification_delivery_runs
                    WHERE notification_type = 'news'
                      AND created_at >= datetime('now', '-30 days')
                ), 0) AS news_sent_30d,
                COALESCE((
                    SELECT SUM(sent) FROM notification_delivery_runs
                    WHERE notification_type = 'release'
                      AND created_at >= datetime('now', '-30 days')
                ), 0) AS release_messages_sent_30d,
                COALESCE((
                    SELECT SUM(selected) FROM notification_delivery_runs
                    WHERE created_at >= datetime('now', '-30 days')
                ), 0) AS selected_30d,
                COALESCE((
                    SELECT SUM(sent) FROM notification_delivery_runs
                    WHERE created_at >= datetime('now', '-30 days')
                ), 0) AS sent_30d,
                COALESCE((
                    SELECT SUM(failed) FROM notification_delivery_runs
                    WHERE created_at >= datetime('now', '-30 days')
                ), 0) AS failed_30d,
                COALESCE((
                    SELECT SUM(deactivated) FROM notification_delivery_runs
                    WHERE created_at >= datetime('now', '-30 days')
                ), 0) AS deactivated_30d,
                (
                    SELECT COUNT(*) FROM bot_users WHERE is_active = 0
                ) AS blocked_users,
                (SELECT MAX(created_at) FROM notification_delivery_runs)
                    AS last_delivery_at,
                CURRENT_TIMESTAMP AS generated_at
            """
        ) as cursor:
            row = await cursor.fetchone()

    return AdminNotifications(**dict(row))


async def get_admin_export_users(
    *,
    database_url: str | None = None,
) -> tuple[AdminExportUser, ...]:
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
                COUNT(*) FILTER (WHERE user_media.is_tracking = 1)
                    AS tracked_series
            FROM bot_users
            LEFT JOIN user_media ON user_media.user_id = bot_users.user_id
            GROUP BY bot_users.user_id
            ORDER BY bot_users.user_id
            """
        ) as cursor:
            return tuple(
                AdminExportUser(**dict(row)) for row in await cursor.fetchall()
            )


__all__ = (
    "ADMIN_USERS_PAGE_SIZE",
    "AdminActivity",
    "AdminActivityDay",
    "AdminExportUser",
    "AdminLibraries",
    "AdminNotifications",
    "AdminSystem",
    "AdminOverview",
    "AdminPopularTitle",
    "AdminUserDetails",
    "AdminUserPage",
    "AdminUserSummary",
    "get_admin_overview",
    "get_admin_activity",
    "get_admin_export_users",
    "get_admin_libraries",
    "get_admin_notifications",
    "get_admin_system",
    "get_admin_user",
    "get_admin_users",
    "is_feature_enabled",
    "toggle_feature",
)
