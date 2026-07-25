"""Queries for per-season viewing progress."""

from __future__ import annotations

import aiosqlite

from src.database.connection import connection_scope


async def get_user_season_progress(
    user_id: int,
    media_id: int,
    *,
    database_url: str | None = None,
) -> list[aiosqlite.Row]:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT *
            FROM user_season_progress
            WHERE user_id = ? AND media_id = ?
            ORDER BY season_number
            """,
            (user_id, media_id),
        ) as cursor:
            return await cursor.fetchall()


async def save_user_series_progress(
    *,
    user_id: int,
    media_id: int,
    seasons: dict[int, int],
    total_episodes: int,
    user_rating: int | None = None,
    database_url: str | None = None,
) -> None:
    """Save season details and refresh the aggregate series progress atomically."""
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            INSERT INTO user_media (
                user_id, media_id, status, user_rating, episodes_watched, added_at
            ) VALUES (?, ?, 'watching', ?, 0, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, media_id) DO UPDATE SET
                user_rating = excluded.user_rating,
                last_watched_at = CURRENT_TIMESTAMP
            """,
            (user_id, media_id, user_rating),
        )

        if seasons:
            await connection.executemany(
                """
                INSERT INTO user_season_progress (
                    user_id, media_id, season_number, episodes_watched
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, media_id, season_number) DO UPDATE SET
                    episodes_watched = excluded.episodes_watched,
                    last_watched_at = CURRENT_TIMESTAMP
                """,
                [
                    (user_id, media_id, season_number, episodes_watched)
                    for season_number, episodes_watched in seasons.items()
                ],
            )

        async with connection.execute(
            """
            SELECT COALESCE(SUM(episodes_watched), 0)
            FROM user_season_progress
            WHERE user_id = ? AND media_id = ?
            """,
            (user_id, media_id),
        ) as cursor:
            episodes_watched = int((await cursor.fetchone())[0])

        status = (
            "completed"
            if total_episodes > 0 and episodes_watched >= total_episodes
            else "watching"
        )
        await connection.execute(
            """
            UPDATE user_media
            SET status = ?, episodes_watched = ?, last_watched_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND media_id = ?
            """,
            (status, episodes_watched, user_id, media_id),
        )


__all__ = ("get_user_season_progress", "save_user_series_progress")
