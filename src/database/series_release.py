"""Persistence of shared series release metadata."""

from __future__ import annotations

import aiosqlite

from src.database.connection import connection_scope, existing_or_connection_scope
from src.models import SeriesReleaseSnapshot


async def update_media_series_release_info(
    media_id: int,
    *,
    user_id: int,
    snapshot: SeriesReleaseSnapshot,
    database_url: str | None = None,
    connection: aiosqlite.Connection | None = None,
) -> None:
    """Refresh shared release data without changing any user's progress."""
    available_episode_count = snapshot.available_episode_count
    next_episode = snapshot.next_episode
    async with existing_or_connection_scope(
        connection,
        database_url=database_url,
    ) as active_connection:
        await _replace_media_seasons(active_connection, media_id, snapshot)
        async with active_connection.execute(
            """
            SELECT COALESCE(MAX(season_number), 0),
                   COALESCE(SUM(announced_episode_count), 0),
                   COALESCE(SUM(available_episode_count), 0)
            FROM media_seasons
            WHERE media_id = ?
            """,
            (media_id,),
        ) as cursor:
            season_count, announced_count, available_count = await cursor.fetchone()
        async with active_connection.execute(
            """
            SELECT COALESCE(MAX(episodes_watched), 0)
            FROM user_media
            WHERE media_id = ?
            """,
            (media_id,),
        ) as cursor:
            max_user_progress = int((await cursor.fetchone())[0])

        consistent_available = max(
            available_episode_count,
            int(available_count),
            max_user_progress,
        )
        consistent_seasons = max(snapshot.number_of_seasons, int(season_count))
        consistent_episodes = max(
            snapshot.number_of_episodes,
            int(announced_count),
            consistent_available,
        )
        await active_connection.execute(
            """
            UPDATE media
            SET tmdb_status = ?, tmdb_in_production = ?,
                number_of_seasons = ?,
                number_of_episodes = ?,
                available_episode_count = ?,
                poster_path = COALESCE(?, poster_path),
                rating = COALESCE(?, rating),
                next_episode_air_date = ?, next_episode_season_number = ?,
                next_episode_number = ?,
                tmdb_release_checked_at = CURRENT_TIMESTAMP,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                snapshot.status,
                snapshot.in_production,
                consistent_seasons,
                consistent_episodes,
                consistent_available,
                snapshot.poster_path,
                snapshot.rating,
                next_episode.air_date if next_episode is not None else None,
                next_episode.season_number if next_episode is not None else None,
                next_episode.episode_number if next_episode is not None else None,
                media_id,
            ),
        )


async def replace_media_seasons(
    media_id: int,
    snapshot: SeriesReleaseSnapshot,
    *,
    database_url: str | None = None,
) -> None:
    """Merge current release data without losing saved user progress."""
    async with connection_scope(database_url) as connection:
        await _replace_media_seasons(connection, media_id, snapshot)


async def _replace_media_seasons(
    connection: aiosqlite.Connection,
    media_id: int,
    snapshot: SeriesReleaseSnapshot,
) -> None:
    seasons = snapshot.regular_seasons
    if seasons:
        async with connection.execute(
            """
            SELECT season_number, MAX(episodes_watched) AS episodes_watched
            FROM user_season_progress
            WHERE media_id = ?
            GROUP BY season_number
            """,
            (media_id,),
        ) as cursor:
            progress_by_season = {
                int(row["season_number"]): int(row["episodes_watched"])
                for row in await cursor.fetchall()
            }

        await connection.executemany(
            """
            INSERT INTO media_seasons (
                media_id, season_number, name,
                announced_episode_count, available_episode_count
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(media_id, season_number) DO UPDATE SET
                name = excluded.name,
                announced_episode_count = excluded.announced_episode_count,
                available_episode_count = excluded.available_episode_count,
                last_updated = CURRENT_TIMESTAMP
            """,
            [
                (
                    media_id,
                    season.season_number,
                    season.name,
                    max(
                        season.announced_episode_count,
                        progress_by_season.get(season.season_number, 0),
                    ),
                    max(
                        season.aired_episode_count,
                        progress_by_season.get(season.season_number, 0),
                    ),
                )
                for season in seasons
            ],
        )


__all__ = (
    "replace_media_seasons",
    "update_media_series_release_info",
)
