import sqlite3

from src.database.connection import connection_scope
from src.database.media import get_media_by_tmdb
from src.database.ratings import get_user_rating_details
from src.database.series import (
    get_user_season_progress,
    save_user_series_progress,
)
from src.database.series_release import update_media_series_release_info
from src.database.user_media import get_user_media
from src.models import SeriesReleaseSnapshot, SeriesSeason
from src.tmdb_models import TmdbEpisodeAirInfo
from tests.support.database import DatabaseTestCase


class SeriesTests(DatabaseTestCase):
    async def test_series_release_info_is_overwritten(self) -> None:
        media_id = await self.create_series(
            tmdb_id=45,
            title="Active series",
        )
        await update_media_series_release_info(
            media_id,
            user_id=123,
            snapshot=SeriesReleaseSnapshot(
                number_of_seasons=2,
                number_of_episodes=16,
                seasons=[SeriesSeason(1, "Season 1", 12, 12)],
                status="Returning Series",
                in_production=True,
                next_episode_to_air=TmdbEpisodeAirInfo(2, 5, "2026-08-10"),
            ),
            database_url=self.database_url,
        )
        await update_media_series_release_info(
            media_id,
            user_id=123,
            snapshot=SeriesReleaseSnapshot(
                number_of_seasons=2,
                number_of_episodes=17,
                seasons=[
                    SeriesSeason(1, "Season 1", 12, 12),
                    SeriesSeason(2, "Season 2", 5, 1),
                ],
                status="Returning Series",
                in_production=True,
                next_episode_to_air=TmdbEpisodeAirInfo(2, 6, "2026-08-17"),
                poster_path="/new.jpg",
                rating=8.4,
            ),
            database_url=self.database_url,
        )

        row = await get_media_by_tmdb(
            45,
            "series",
            "movie",
            database_url=self.database_url,
        )
        self.assertEqual(row["tmdb_status"], "Returning Series")
        self.assertEqual(row["tmdb_in_production"], 1)
        self.assertEqual(row["number_of_episodes"], 17)
        self.assertEqual(row["available_episode_count"], 13)
        self.assertEqual(row["poster_path"], "/new.jpg")
        self.assertEqual(row["rating"], 8.4)
        self.assertEqual(row["next_episode_air_date"], "2026-08-17")
        self.assertEqual(row["next_episode_season_number"], 2)
        self.assertEqual(row["next_episode_number"], 6)
        self.assertIsNotNone(row["tmdb_release_checked_at"])

        async with connection_scope(self.database_url) as connection:
            async with connection.execute(
                """
                SELECT season_number, announced_episode_count,
                       available_episode_count
                FROM media_seasons
                WHERE media_id = ?
                ORDER BY season_number
                """,
                (media_id,),
            ) as cursor:
                seasons = await cursor.fetchall()
        self.assertEqual(
            [tuple(season) for season in seasons],
            [(1, 12, 12), (2, 5, 1)],
        )

    async def test_series_release_refresh_does_not_change_other_users(self) -> None:
        media_id = await self.create_series(
            tmdb_id=46,
            title="Shared series",
            number_of_seasons=1,
            number_of_episodes=10,
            available_episode_count=10,
        )
        for user_id in (123, 456):
            await save_user_series_progress(
                user_id=user_id,
                media_id=media_id,
                seasons={1: 8},
                total_episodes=10,
                database_url=self.database_url,
            )
        async with connection_scope(self.database_url) as connection:
            await connection.execute(
                """
                UPDATE user_media
                SET status = 'on_hold', last_watched_at = '2000-01-01 00:00:00'
                WHERE user_id = 456 AND media_id = ?
                """,
                (media_id,),
            )

        await update_media_series_release_info(
            media_id,
            user_id=123,
            snapshot=SeriesReleaseSnapshot(
                number_of_seasons=1,
                number_of_episodes=10,
                seasons=[SeriesSeason(1, "Season 1", 10, 5)],
                status="Returning Series",
                in_production=True,
            ),
            database_url=self.database_url,
        )

        initiating_user = await get_user_media(
            123, media_id, database_url=self.database_url
        )
        other_user = await get_user_media(456, media_id, database_url=self.database_url)
        initiating_progress = await get_user_season_progress(
            123, media_id, database_url=self.database_url
        )
        other_progress = await get_user_season_progress(
            456, media_id, database_url=self.database_url
        )

        self.assertEqual(initiating_user["episodes_watched"], 5)
        self.assertEqual(initiating_progress[0]["episodes_watched"], 5)
        self.assertEqual(other_user["episodes_watched"], 8)
        self.assertEqual(other_user["status"], "on_hold")
        self.assertEqual(other_user["last_watched_at"], "2000-01-01 00:00:00")
        self.assertEqual(other_progress[0]["episodes_watched"], 8)

    async def test_season_progress_is_inserted_and_updated(self) -> None:
        media_id = await self.create_series()
        await save_user_series_progress(
            user_id=123,
            media_id=media_id,
            seasons={1: 3},
            total_episodes=20,
            database_url=self.database_url,
        )
        await save_user_series_progress(
            user_id=123,
            media_id=media_id,
            seasons={1: 8, 2: 2},
            total_episodes=20,
            database_url=self.database_url,
        )

        rows = await get_user_season_progress(
            123,
            media_id,
            database_url=self.database_url,
        )

        self.assertEqual(
            [(row["season_number"], row["episodes_watched"]) for row in rows],
            [(1, 8), (2, 2)],
        )

    async def test_series_progress_update_preserves_detailed_ratings(self) -> None:
        media_id = await self.create_series(
            tmdb_id=146,
            title="Rated series",
        )
        ratings = {
            "acting": 8,
            "story": 9,
            "visuals": 7,
            "sound": 8,
            "overall": 9,
        }
        await save_user_series_progress(
            user_id=123,
            media_id=media_id,
            seasons={1: 2},
            total_episodes=10,
            user_rating=8,
            rating_details=ratings,
            database_url=self.database_url,
        )
        await save_user_series_progress(
            user_id=123,
            media_id=media_id,
            seasons={1: 3},
            total_episodes=10,
            user_rating=8,
            rating_details=None,
            database_url=self.database_url,
        )

        self.assertEqual(
            await get_user_rating_details(
                123, media_id, database_url=self.database_url
            ),
            ratings,
        )

    async def test_caught_up_active_series_stays_watching(self) -> None:
        media_id = await self.create_series(
            tmdb_id=43,
            title="Active TV",
            number_of_episodes=12,
            available_episode_count=5,
        )
        await save_user_series_progress(
            user_id=123,
            media_id=media_id,
            seasons={1: 5},
            total_episodes=5,
            is_ongoing=True,
            database_url=self.database_url,
        )

        progress = await get_user_media(
            123,
            media_id,
            database_url=self.database_url,
        )

        self.assertEqual(progress["episodes_watched"], 5)
        self.assertEqual(progress["status"], "watching")

    async def test_deleting_user_media_cascades_to_season_progress(self) -> None:
        media_id = await self.create_series()
        await save_user_series_progress(
            user_id=123,
            media_id=media_id,
            seasons={1: 3},
            total_episodes=10,
            database_url=self.database_url,
        )

        async with connection_scope(self.database_url) as connection:
            await connection.execute(
                "DELETE FROM user_media WHERE user_id = ? AND media_id = ?",
                (123, media_id),
            )

        self.assertEqual(
            await get_user_season_progress(
                123,
                media_id,
                database_url=self.database_url,
            ),
            [],
        )

    async def test_series_progress_updates_user_media_aggregate(self) -> None:
        media_id = await self.create_series()

        await save_user_series_progress(
            user_id=123,
            media_id=media_id,
            seasons={1: 8, 2: 2},
            total_episodes=10,
            user_rating=9,
            database_url=self.database_url,
        )

        row = await get_user_media(123, media_id, database_url=self.database_url)
        self.assertEqual(row["episodes_watched"], 10)
        self.assertEqual(row["status"], "completed")
        self.assertEqual(row["user_rating"], 9)

    async def test_series_progress_rejects_invalid_values_before_writing(self) -> None:
        media_id = await self.create_series()
        invalid_progress = (
            ({-1: 1}, 10),
            ({0: 1}, 10),
            ({1: -1}, 10),
            ({1: 11}, 10),
            ({1: 0}, 10),
            ({}, 10),
        )

        for seasons, total in invalid_progress:
            with self.subTest(seasons=seasons):
                with self.assertRaises(ValueError):
                    await save_user_series_progress(
                        user_id=123,
                        media_id=media_id,
                        seasons=seasons,
                        total_episodes=total,
                        database_url=self.database_url,
                    )

        self.assertEqual(
            await get_user_season_progress(
                123,
                media_id,
                database_url=self.database_url,
            ),
            [],
        )

    async def test_database_trigger_rejects_aggregate_above_series_total(self) -> None:
        media_id = await self.create_series(
            tmdb_id=42,
            title="TV",
            number_of_seasons=2,
            number_of_episodes=10,
        )
        await self.create_user_media(
            user_id=123,
            media_id=media_id,
            status="watching",
            episodes_watched=0,
        )

        with self.assertRaises(sqlite3.IntegrityError):
            async with connection_scope(self.database_url) as connection:
                await connection.execute(
                    """
                    INSERT INTO user_season_progress (
                        user_id, media_id, season_number, episodes_watched
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (123, media_id, 1, 11),
                )

    async def test_database_trigger_rejects_special_season_progress(self) -> None:
        media_id = await self.create_series(
            tmdb_id=42,
            title="TV",
            number_of_seasons=1,
            number_of_episodes=10,
        )
        await self.create_user_media(
            user_id=123,
            media_id=media_id,
            status="watching",
            episodes_watched=0,
        )

        with self.assertRaises(sqlite3.IntegrityError):
            async with connection_scope(self.database_url) as connection:
                await connection.execute(
                    """
                    INSERT INTO user_season_progress (
                        user_id, media_id, season_number, episodes_watched
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (123, media_id, 0, 1),
                )

    async def test_series_progress_cannot_be_saved_for_movie(self) -> None:
        media_id = await self.create_media(
            tmdb_id=42,
            content_format="full_length",
            content_type="movie",
            title="Movie",
        )

        with self.assertRaises(ValueError):
            await save_user_series_progress(
                user_id=123,
                media_id=media_id,
                seasons={1: 1},
                total_episodes=10,
                database_url=self.database_url,
            )
