"""Queries for per-season viewing progress."""

from __future__ import annotations

from collections.abc import Mapping

import aiosqlite

from src.database.connection import connection_scope, existing_or_connection_scope
from src.database.ratings import replace_user_rating_details


async def get_media_seasons(
    media_id: int,
    *,
    database_url: str | None = None,
) -> list[aiosqlite.Row]:
    """Return cached regular seasons for one catalogue entry."""
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT season_number, name,
                   announced_episode_count, available_episode_count
            FROM media_seasons
            WHERE media_id = ?
            ORDER BY season_number
            """,
            (media_id,),
        ) as cursor:
            return await cursor.fetchall()


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
    is_ongoing: bool = False,
    user_rating: int | None = None,
    rating_details: Mapping[str, int] | None = None,
    database_url: str | None = None,
    connection: aiosqlite.Connection | None = None,
) -> None:
    """Save season details and refresh the aggregate series progress atomically."""
    _validate_progress_values(seasons, total_episodes)

    async with existing_or_connection_scope(
        connection,
        database_url=database_url,
    ) as active_connection:
        async with active_connection.execute(
            "SELECT content_format FROM media WHERE id = ?",
            (media_id,),
        ) as cursor:
            media = await cursor.fetchone()
        if media is None:
            raise ValueError("Series media does not exist")
        if media["content_format"] != "series":
            raise ValueError("Progress can only be saved for series")

        await active_connection.execute(
            """
            INSERT INTO user_media (
                user_id, media_id, status, user_rating, episodes_watched, added_at
            ) VALUES (?, ?, 'watching', ?, 0, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, media_id) DO UPDATE SET
                status = 'watching',
                user_rating = excluded.user_rating,
                episodes_watched = 0,
                last_watched_at = CURRENT_TIMESTAMP
            """,
            (user_id, media_id, user_rating),
        )
        if rating_details is not None:
            await replace_user_rating_details(
                active_connection,
                user_id,
                media_id,
                rating_details,
            )

        await active_connection.execute(
            "DELETE FROM user_season_progress WHERE user_id = ? AND media_id = ?",
            (user_id, media_id),
        )
        await active_connection.execute(
            """
            UPDATE media
            SET available_episode_count = ?, last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (total_episodes, media_id),
        )
        if seasons:
            await active_connection.executemany(
                """
                INSERT INTO user_season_progress (
                    user_id, media_id, season_number, episodes_watched
                ) VALUES (?, ?, ?, ?)
                """,
                [
                    (user_id, media_id, season_number, episodes_watched)
                    for season_number, episodes_watched in seasons.items()
                ],
            )

        async with active_connection.execute(
            """
            SELECT COALESCE(SUM(episodes_watched), 0)
            FROM user_season_progress
            WHERE user_id = ? AND media_id = ?
            """,
            (user_id, media_id),
        ) as cursor:
            episodes_watched = int((await cursor.fetchone())[0])

        if episodes_watched == 0:
            status = "planned"
        elif (
            not is_ongoing and total_episodes > 0 and episodes_watched == total_episodes
        ):
            status = "completed"
        else:
            status = "watching"
        await active_connection.execute(
            """
            UPDATE user_media
            SET status = ?, episodes_watched = ?, last_watched_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND media_id = ?
            """,
            (status, episodes_watched, user_id, media_id),
        )


def _validate_progress_values(seasons: dict[int, int], total_episodes: int) -> None:
    if type(total_episodes) is not int or total_episodes < 0:
        raise ValueError("total_episodes must be a non-negative integer")

    for season_number, episodes_watched in seasons.items():
        if type(season_number) is not int or season_number <= 0:
            raise ValueError("season numbers must be positive integers")
        if type(episodes_watched) is not int or episodes_watched < 0:
            raise ValueError("episode counts must be non-negative integers")

    if sum(seasons.values()) > total_episodes:
        raise ValueError("watched episodes cannot exceed total episodes")
    if sum(seasons.values()) == 0:
        raise ValueError("at least one watched episode is required")


__all__ = (
    "get_media_seasons",
    "get_user_season_progress",
    "save_user_series_progress",
)
