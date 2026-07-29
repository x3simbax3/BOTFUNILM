"""Persistence of shared series release metadata."""

from __future__ import annotations

import aiosqlite

from src.database.connection import connection_scope
from src.models import SeriesReleaseSnapshot


async def update_media_series_release_info(
    media_id: int,
    *,
    user_id: int,
    snapshot: SeriesReleaseSnapshot,
    database_url: str | None = None,
) -> None:
    """Refresh release data and reconcile only the initiating user's progress."""
    available_episode_count = snapshot.available_episode_count
    next_episode = snapshot.next_episode
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            UPDATE media
            SET tmdb_status = ?, tmdb_in_production = ?,
                number_of_seasons = ?, number_of_episodes = ?,
                available_episode_count = MAX(?, COALESCE((
                    SELECT MAX(episodes_watched)
                    FROM user_media
                    WHERE media_id = ?
                ), 0)),
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
                snapshot.number_of_seasons,
                snapshot.number_of_episodes,
                available_episode_count,
                media_id,
                snapshot.poster_path,
                snapshot.rating,
                next_episode.air_date if next_episode is not None else None,
                next_episode.season_number if next_episode is not None else None,
                next_episode.episode_number if next_episode is not None else None,
                media_id,
            ),
        )
        await _replace_media_seasons(connection, media_id, snapshot)
        await connection.execute(
            """
            UPDATE user_season_progress
            SET episodes_watched = (
                    SELECT ms.available_episode_count
                    FROM media_seasons AS ms
                    WHERE ms.media_id = user_season_progress.media_id
                      AND ms.season_number = user_season_progress.season_number
                ),
                last_watched_at = CURRENT_TIMESTAMP
            WHERE media_id = ? AND user_id = ?
              AND EXISTS (
                  SELECT 1 FROM media_seasons AS ms
                  WHERE ms.media_id = user_season_progress.media_id
                    AND ms.season_number = user_season_progress.season_number
                    AND user_season_progress.episodes_watched
                        > ms.available_episode_count
              )
            """,
            (media_id, user_id),
        )
        await connection.execute(
            """
            UPDATE user_media
            SET episodes_watched = COALESCE((
                    SELECT SUM(usp.episodes_watched)
                    FROM user_season_progress AS usp
                    WHERE usp.user_id = user_media.user_id
                      AND usp.media_id = user_media.media_id
                ), 0),
                status = CASE
                    WHEN COALESCE((
                        SELECT SUM(usp.episodes_watched)
                        FROM user_season_progress AS usp
                        WHERE usp.user_id = user_media.user_id
                          AND usp.media_id = user_media.media_id
                    ), 0) = 0 THEN 'planned'
                    WHEN ? THEN 'watching'
                    WHEN COALESCE((
                        SELECT SUM(usp.episodes_watched)
                        FROM user_season_progress AS usp
                        WHERE usp.user_id = user_media.user_id
                          AND usp.media_id = user_media.media_id
                    ), 0) = ? THEN 'completed'
                    ELSE 'watching'
                END,
                last_watched_at = CURRENT_TIMESTAMP
            WHERE media_id = ? AND user_id = ?
            """,
            (snapshot.active, available_episode_count, media_id, user_id),
        )
        await connection.execute(
            "UPDATE media SET available_episode_count = ? WHERE id = ?",
            (available_episode_count, media_id),
        )


async def replace_media_seasons(
    media_id: int,
    snapshot: SeriesReleaseSnapshot,
    *,
    database_url: str | None = None,
) -> None:
    """Replace cached season availability from one release snapshot."""
    async with connection_scope(database_url) as connection:
        await _replace_media_seasons(connection, media_id, snapshot)


async def _replace_media_seasons(
    connection: aiosqlite.Connection,
    media_id: int,
    snapshot: SeriesReleaseSnapshot,
) -> None:
    await connection.execute(
        "DELETE FROM media_seasons WHERE media_id = ?", (media_id,)
    )
    seasons = snapshot.regular_seasons
    if seasons:
        await connection.executemany(
            """
            INSERT INTO media_seasons (
                media_id, season_number, name,
                announced_episode_count, available_episode_count
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    media_id,
                    season.season_number,
                    season.name,
                    season.announced_episode_count,
                    season.aired_episode_count,
                )
                for season in seasons
            ],
        )


__all__ = (
    "replace_media_seasons",
    "update_media_series_release_info",
)
