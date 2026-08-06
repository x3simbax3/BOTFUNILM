"""Admin queries for users and user export."""

from __future__ import annotations

from src.database.admin.models import (
    ADMIN_EXPORT_USERS_LIMIT,
    ADMIN_USERS_PAGE_SIZE,
    AdminExportUser,
    AdminOverview,
    AdminUserDetails,
    AdminUserPage,
    AdminUserSummary,
)
from src.database.connection import connection_scope


async def get_admin_overview(*, database_url: str | None = None) -> AdminOverview:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT
                COUNT(*) AS total_users,
                COUNT(*) FILTER (WHERE is_active = 1) AS active_users,
                COUNT(*) FILTER (WHERE is_active = 0) AS inactive_users,
                COUNT(*) FILTER (WHERE started_at >= datetime('now', '-1 day')) AS new_24h,
                COUNT(*) FILTER (WHERE started_at >= datetime('now', '-7 days')) AS new_7d,
                COUNT(*) FILTER (WHERE started_at >= datetime('now', '-30 days')) AS new_30d,
                COUNT(*) FILTER (WHERE last_activity_at >= datetime('now', '-1 day')) AS active_24h,
                COUNT(*) FILTER (WHERE last_activity_at >= datetime('now', '-7 days')) AS active_7d,
                COUNT(*) FILTER (WHERE last_activity_at >= datetime('now', '-30 days')) AS active_30d,
                COUNT(*) FILTER (WHERE EXISTS (
                    SELECT 1 FROM user_media WHERE user_media.user_id = bot_users.user_id
                )) AS activated_users,
                (SELECT COUNT(*) FROM user_media) AS library_items,
                (SELECT COUNT(*) FROM user_media WHERE user_rating IS NOT NULL) AS rated_items,
                (SELECT COUNT(*) FROM user_media WHERE is_tracking = 1) AS tracked_series,
                COUNT(*) FILTER (WHERE is_active = 1 AND news_enabled = 1) AS news_users,
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
            SELECT bot_users.user_id, bot_users.username, bot_users.display_name,
                   bot_users.is_active, bot_users.started_at, bot_users.last_activity_at,
                   COUNT(user_media.media_id) AS library_items
            FROM bot_users
            LEFT JOIN user_media ON user_media.user_id = bot_users.user_id
            GROUP BY bot_users.user_id
            ORDER BY bot_users.last_activity_at DESC, bot_users.user_id
            LIMIT ? OFFSET ?
            """,
            (page_size, (current_page - 1) * page_size),
        ) as cursor:
            users = tuple(AdminUserSummary(**dict(row)) for row in await cursor.fetchall())
    return AdminUserPage(users, current_page, total_pages, total_users)


async def get_admin_user(
    user_id: int, *, database_url: str | None = None
) -> AdminUserDetails | None:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT bot_users.user_id, bot_users.username, bot_users.display_name,
                   bot_users.is_active, bot_users.news_enabled, bot_users.started_at,
                   bot_users.last_started_at, bot_users.last_activity_at,
                   COUNT(user_media.media_id) AS library_items,
                   COUNT(*) FILTER (WHERE user_media.status = 'planned') AS planned_items,
                   COUNT(*) FILTER (WHERE user_media.status = 'watching') AS watching_items,
                   COUNT(*) FILTER (WHERE user_media.status = 'completed') AS completed_items,
                   COUNT(*) FILTER (WHERE user_media.status = 'on_hold') AS on_hold_items,
                   COUNT(*) FILTER (WHERE user_media.user_rating IS NOT NULL) AS rated_items,
                   AVG(user_media.user_rating) AS average_rating,
                   COUNT(*) FILTER (WHERE user_media.is_tracking = 1) AS tracked_series
            FROM bot_users
            LEFT JOIN user_media ON user_media.user_id = bot_users.user_id
            WHERE bot_users.user_id = ?
            GROUP BY bot_users.user_id
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
    return None if row is None else AdminUserDetails(**dict(row))


async def get_admin_export_users(
    *, limit: int = ADMIN_EXPORT_USERS_LIMIT, database_url: str | None = None
) -> tuple[AdminExportUser, ...]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT bot_users.user_id, bot_users.username, bot_users.display_name,
                   bot_users.is_active, bot_users.news_enabled, bot_users.started_at,
                   bot_users.last_started_at, bot_users.last_activity_at,
                   COUNT(user_media.media_id) AS library_items,
                   COUNT(*) FILTER (WHERE user_media.status = 'planned') AS planned_items,
                   COUNT(*) FILTER (WHERE user_media.status = 'watching') AS watching_items,
                   COUNT(*) FILTER (WHERE user_media.status = 'completed') AS completed_items,
                   COUNT(*) FILTER (WHERE user_media.status = 'on_hold') AS on_hold_items,
                   COUNT(*) FILTER (WHERE user_media.user_rating IS NOT NULL) AS rated_items,
                   COUNT(*) FILTER (WHERE user_media.is_tracking = 1) AS tracked_series
            FROM bot_users
            LEFT JOIN user_media ON user_media.user_id = bot_users.user_id
            GROUP BY bot_users.user_id
            ORDER BY bot_users.user_id
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            return tuple(AdminExportUser(**dict(row)) for row in await cursor.fetchall())
