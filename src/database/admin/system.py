"""Admin queries for system state and runtime features."""

from __future__ import annotations

from src.database.admin.models import ALLOWED_FEATURES, AdminSystem
from src.database.connection import connection_scope


async def get_admin_system(*, database_url: str | None = None) -> AdminSystem:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT
                COUNT(*) AS catalog_items,
                COUNT(*) FILTER (WHERE tmdb_refresh_error IS NOT NULL) AS tmdb_errors,
                COUNT(*) FILTER (
                    WHERE tmdb_id IS NOT NULL
                      AND ((content_format = 'series' AND (tmdb_in_production = 1
                           OR tmdb_status IN ('Returning Series', 'Planned', 'In Production')))
                           OR (is_released = 0 AND EXISTS (
                               SELECT 1 FROM user_media
                               WHERE user_media.media_id = media.id
                                 AND user_media.status = 'planned')))
                      AND (tmdb_release_checked_at IS NULL
                           OR tmdb_release_checked_at < datetime('now', '-23 hours'))
                ) AS daily_overdue,
                COUNT(*) FILTER (
                    WHERE tmdb_id IS NOT NULL AND content_format = 'series'
                      AND (tmdb_metadata_checked_at IS NULL
                           OR tmdb_metadata_checked_at < datetime('now', '-6 days 23 hours'))
                ) AS weekly_overdue,
                (SELECT COUNT(*) FROM user_series_notifications AS n
                 LEFT JOIN series_notification_batches AS b ON b.id = n.batch_id
                 WHERE n.batch_id IS NULL OR b.sent_at IS NULL) AS pending_series_notifications,
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
        async with connection.execute("SELECT feature, enabled FROM bot_features") as cursor:
            features = {row["feature"]: row["enabled"] for row in await cursor.fetchall()}

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
