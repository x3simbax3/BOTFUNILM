import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.database.connection import connect_database, connection_scope, database_path
from src.database.library import (
    get_user_library_filters,
    get_user_library_item,
    list_user_library,
    update_user_library_filter,
)
from src.database.media import (
    find_media_by_title,
    get_media_by_tmdb,
    update_media_poster,
    update_media_series_release_info,
    upsert_media,
)
from src.database.series import (
    get_user_season_progress,
    save_user_series_progress,
)
from src.database.user_media import (
    delete_user_media,
    get_user_media,
    save_user_media,
    set_user_media_status,
    update_user_media_rating,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = sorted((PROJECT_ROOT / "migrations").glob("*.sql"))


class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        database_file = Path(self._temporary_directory.name) / "test.db"
        self.database_url = f"sqlite:///{database_file}"

        with sqlite3.connect(database_file) as connection:
            for migration in MIGRATIONS:
                connection.executescript(migration.read_text(encoding="utf-8"))

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    async def test_migration_creates_tables_and_indexes(self) -> None:
        async with connection_scope(self.database_url) as connection:
            async with connection.execute(
                "SELECT name, type FROM sqlite_master"
            ) as cursor:
                objects = {
                    (row["name"], row["type"]) for row in await cursor.fetchall()
                }

        self.assertIn(("media", "table"), objects)
        self.assertIn(("user_media", "table"), objects)
        self.assertIn(("user_season_progress", "table"), objects)
        self.assertIn(("user_library_filters", "table"), objects)
        self.assertIn(("ix_media_status", "index"), objects)
        self.assertIn(("ix_user_media_media_id", "index"), objects)
        self.assertIn(("ix_user_season_progress_media_id", "index"), objects)
        self.assertIn(
            ("update_media_library_users_count_after_insert", "trigger"),
            objects,
        )
        self.assertIn(
            ("update_media_library_users_count_after_delete", "trigger"),
            objects,
        )

    async def test_upsert_media_inserts_and_updates(self) -> None:
        media_id = await upsert_media(
            tmdb_id=42,
            content_format="full_length",
            content_type="movie",
            title="Old title",
            database_url=self.database_url,
        )
        updated_id = await upsert_media(
            tmdb_id=42,
            content_format="full_length",
            content_type="movie",
            title="New title",
            rating=8.5,
            database_url=self.database_url,
        )
        row = await get_media_by_tmdb(
            42,
            "full_length",
            "movie",
            database_url=self.database_url,
        )

        self.assertEqual(updated_id, media_id)
        self.assertEqual(row["title"], "New title")
        self.assertEqual(row["rating"], 8.5)

    async def test_update_media_poster(self) -> None:
        media_id = await upsert_media(
            tmdb_id=42,
            content_format="full_length",
            content_type="movie",
            title="Movie",
            poster_path="/old.jpg",
            database_url=self.database_url,
        )

        await update_media_poster(
            media_id,
            "posters/tmdb_movie_42.jpg",
            database_url=self.database_url,
        )
        row = await get_media_by_tmdb(
            42,
            "full_length",
            "movie",
            database_url=self.database_url,
        )

        self.assertEqual(row["poster_path"], "posters/tmdb_movie_42.jpg")

    async def test_series_release_info_is_overwritten(self) -> None:
        media_id = await upsert_media(
            tmdb_id=45,
            content_format="series",
            content_type="movie",
            title="Active series",
            database_url=self.database_url,
        )
        await update_media_series_release_info(
            media_id,
            status="Returning Series",
            in_production=True,
            number_of_seasons=2,
            number_of_episodes=16,
            poster_path=None,
            rating=None,
            next_episode_air_date="2026-08-10",
            next_episode_season_number=2,
            next_episode_number=5,
            database_url=self.database_url,
        )
        await update_media_series_release_info(
            media_id,
            status="Returning Series",
            in_production=True,
            number_of_seasons=2,
            number_of_episodes=17,
            poster_path="/new.jpg",
            rating=8.4,
            next_episode_air_date="2026-08-17",
            next_episode_season_number=2,
            next_episode_number=6,
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
        self.assertEqual(row["poster_path"], "/new.jpg")
        self.assertEqual(row["rating"], 8.4)
        self.assertEqual(row["next_episode_air_date"], "2026-08-17")
        self.assertEqual(row["next_episode_season_number"], 2)
        self.assertEqual(row["next_episode_number"], 6)
        self.assertIsNotNone(row["tmdb_release_checked_at"])

    async def test_same_tmdb_id_is_allowed_for_different_classifications(self) -> None:
        movie_id = await upsert_media(
            tmdb_id=42,
            content_format="full_length",
            content_type="movie",
            title="Movie",
            database_url=self.database_url,
        )
        tv_id = await upsert_media(
            tmdb_id=42,
            content_format="series",
            content_type="movie",
            title="TV",
            database_url=self.database_url,
        )

        self.assertNotEqual(movie_id, tv_id)

    async def test_manual_media_can_have_null_tmdb_id(self) -> None:
        first = await upsert_media(
            tmdb_id=None,
            content_format="full_length",
            content_type="movie",
            title="Manual one",
            database_url=self.database_url,
        )
        second = await upsert_media(
            tmdb_id=None,
            content_format="full_length",
            content_type="movie",
            title="Manual two",
            database_url=self.database_url,
        )

        self.assertNotEqual(first, second)

    async def test_find_media_by_title_normalizes_and_matches_typos(self) -> None:
        expected_id = await upsert_media(
            tmdb_id=42,
            content_format="series",
            content_type="anime",
            title="О моём перерождении в слизь",
            original_title="Tensei Shitara Slime Datta Ken",
            database_url=self.database_url,
        )

        row = await find_media_by_title(
            "о моем перерождении в сизь",
            "series",
            "anime",
            database_url=self.database_url,
        )

        self.assertIsNotNone(row)
        self.assertEqual(row["id"], expected_id)

    async def test_find_media_by_title_respects_classification(self) -> None:
        await upsert_media(
            tmdb_id=42,
            content_format="full_length",
            content_type="movie",
            title="Матрица",
            database_url=self.database_url,
        )

        row = await find_media_by_title(
            "Матрица",
            "series",
            "movie",
            database_url=self.database_url,
        )

        self.assertIsNone(row)

    async def test_user_media_is_inserted_and_updated(self) -> None:
        media_id = await upsert_media(
            tmdb_id=42,
            content_format="series",
            content_type="anime",
            title="Anime",
            database_url=self.database_url,
        )
        await save_user_media(
            user_id=123,
            media_id=media_id,
            status="watching",
            episodes_watched=3,
            database_url=self.database_url,
        )
        await save_user_media(
            user_id=123,
            media_id=media_id,
            status="completed",
            user_rating=9,
            episodes_watched=12,
            database_url=self.database_url,
        )
        row = await get_user_media(123, media_id, database_url=self.database_url)

        self.assertEqual(row["status"], "completed")
        self.assertEqual(row["user_rating"], 9)
        self.assertEqual(row["episodes_watched"], 12)

    async def test_media_library_users_count_tracks_additions_and_deletions(
        self,
    ) -> None:
        media_id = await upsert_media(
            tmdb_id=44,
            content_format="full_length",
            content_type="movie",
            title="Popular movie",
            database_url=self.database_url,
        )
        await save_user_media(
            user_id=123,
            media_id=media_id,
            status="planned",
            database_url=self.database_url,
        )
        await save_user_media(
            user_id=456,
            media_id=media_id,
            status="completed",
            database_url=self.database_url,
        )
        await save_user_media(
            user_id=123,
            media_id=media_id,
            status="completed",
            database_url=self.database_url,
        )

        media = await get_media_by_tmdb(
            44,
            "full_length",
            "movie",
            database_url=self.database_url,
        )
        self.assertEqual(media["library_users_count"], 2)

        self.assertTrue(
            await delete_user_media(123, media_id, database_url=self.database_url)
        )
        self.assertFalse(
            await delete_user_media(123, media_id, database_url=self.database_url)
        )
        media = await get_media_by_tmdb(
            44,
            "full_length",
            "movie",
            database_url=self.database_url,
        )
        self.assertEqual(media["library_users_count"], 1)

        self.assertTrue(
            await delete_user_media(456, media_id, database_url=self.database_url)
        )
        media = await get_media_by_tmdb(
            44,
            "full_length",
            "movie",
            database_url=self.database_url,
        )
        self.assertEqual(media["library_users_count"], 0)

    async def test_library_item_status_rating_and_deletion_can_be_changed(self) -> None:
        media_id = await upsert_media(
            tmdb_id=43,
            content_format="full_length",
            content_type="movie",
            title="Planned movie",
            database_url=self.database_url,
        )
        await save_user_media(
            user_id=123,
            media_id=media_id,
            status="planned",
            database_url=self.database_url,
        )

        self.assertTrue(
            await set_user_media_status(
                123, media_id, "completed", database_url=self.database_url
            )
        )
        self.assertTrue(
            await update_user_media_rating(
                123, media_id, 9, database_url=self.database_url
            )
        )
        row = await get_user_media(123, media_id, database_url=self.database_url)
        self.assertEqual(row["status"], "completed")
        self.assertEqual(row["user_rating"], 9)

        self.assertTrue(
            await delete_user_media(123, media_id, database_url=self.database_url)
        )
        self.assertIsNone(
            await get_user_media(123, media_id, database_url=self.database_url)
        )

    async def test_library_filters_are_persisted_per_user(self) -> None:
        defaults = await get_user_library_filters(123, database_url=self.database_url)
        changed = await update_user_library_filter(
            123,
            "anime",
            database_url=self.database_url,
        )
        other_user = await get_user_library_filters(456, database_url=self.database_url)

        self.assertTrue(defaults["completed"])
        self.assertFalse(defaults["planned"])
        self.assertTrue(
            all(value for name, value in defaults.items() if name != "planned")
        )
        self.assertTrue(changed["anime"])
        self.assertFalse(changed["movie"])
        self.assertFalse(changed["cartoon"])
        self.assertTrue(changed["series"])
        self.assertTrue(changed["full_length"])
        self.assertTrue(other_user["completed"])
        self.assertFalse(other_user["planned"])

    async def test_library_filters_are_exclusive_within_each_group(self) -> None:
        series = await update_user_library_filter(
            123,
            "series",
            database_url=self.database_url,
        )
        anime = await update_user_library_filter(
            123,
            "anime",
            database_url=self.database_url,
        )
        planned = await update_user_library_filter(
            123,
            "planned",
            database_url=self.database_url,
        )
        reset = await update_user_library_filter(
            123,
            "all",
            database_url=self.database_url,
        )

        self.assertTrue(series["series"])
        self.assertFalse(series["full_length"])
        self.assertTrue(anime["series"])
        self.assertFalse(anime["full_length"])
        self.assertTrue(anime["anime"])
        self.assertFalse(anime["movie"])
        self.assertFalse(anime["cartoon"])
        self.assertTrue(planned["planned"])
        self.assertFalse(planned["completed"])
        self.assertTrue(reset["completed"])
        self.assertFalse(reset["planned"])
        self.assertTrue(
            all(value for name, value in reset.items() if name != "planned")
        )

    async def test_clicking_selected_filter_restores_its_group(self) -> None:
        for filter_name, group in (
            ("series", ("series", "full_length")),
            ("anime", ("movie", "anime", "cartoon")),
        ):
            with self.subTest(filter_name=filter_name):
                selected = await update_user_library_filter(
                    123,
                    filter_name,
                    database_url=self.database_url,
                )
                restored = await update_user_library_filter(
                    123,
                    filter_name,
                    database_url=self.database_url,
                )

                self.assertTrue(selected[filter_name])
                self.assertTrue(all(restored[name] for name in group))

    async def test_clicking_selected_status_keeps_it_selected(self) -> None:
        selected = await update_user_library_filter(
            123,
            "planned",
            database_url=self.database_url,
        )
        unchanged = await update_user_library_filter(
            123,
            "planned",
            database_url=self.database_url,
        )

        self.assertTrue(selected["planned"])
        self.assertFalse(selected["completed"])
        self.assertEqual(unchanged, selected)

    async def test_library_can_be_filtered_by_watch_status(self) -> None:
        completed_id = await upsert_media(
            tmdb_id=301,
            content_format="full_length",
            content_type="movie",
            title="Просмотрено",
            database_url=self.database_url,
        )
        planned_id = await upsert_media(
            tmdb_id=302,
            content_format="full_length",
            content_type="movie",
            title="На потом",
            database_url=self.database_url,
        )
        watching_id = await upsert_media(
            tmdb_id=303,
            content_format="series",
            content_type="movie",
            title="Начато",
            database_url=self.database_url,
        )
        await save_user_media(
            user_id=123,
            media_id=completed_id,
            status="completed",
            database_url=self.database_url,
        )
        await save_user_media(
            user_id=123,
            media_id=watching_id,
            status="watching",
            episodes_watched=1,
            database_url=self.database_url,
        )
        await save_user_media(
            user_id=123,
            media_id=planned_id,
            status="planned",
            database_url=self.database_url,
        )

        filters = await update_user_library_filter(
            123,
            "planned",
            database_url=self.database_url,
        )
        rows = await list_user_library(
            123,
            filters,
            database_url=self.database_url,
        )

        self.assertEqual([row["title"] for row in rows], ["На потом"])

        completed_filters = await update_user_library_filter(
            123,
            "completed",
            database_url=self.database_url,
        )
        watched_rows = await list_user_library(
            123,
            completed_filters,
            database_url=self.database_url,
        )
        self.assertEqual(
            {row["title"] for row in watched_rows},
            {"Просмотрено", "Начато"},
        )

    async def test_library_is_filtered_and_paginated_newest_first(self) -> None:
        for index in range(25):
            media_id = await upsert_media(
                tmdb_id=index + 1,
                content_format="series" if index % 2 else "full_length",
                content_type="anime" if index % 3 == 0 else "movie",
                title=f"Title {index + 1}",
                database_url=self.database_url,
            )
            await save_user_media(
                user_id=123,
                media_id=media_id,
                status="completed",
                database_url=self.database_url,
            )

        filters = await get_user_library_filters(123, database_url=self.database_url)
        first_page = await list_user_library(
            123,
            filters,
            limit=20,
            database_url=self.database_url,
        )
        second_page = await list_user_library(
            123,
            filters,
            limit=20,
            offset=20,
            database_url=self.database_url,
        )
        filters["series"] = False
        full_length_only = await list_user_library(
            123,
            filters,
            database_url=self.database_url,
        )

        self.assertEqual(len(first_page), 20)
        self.assertEqual(first_page[0]["title"], "Title 25")
        self.assertEqual(len(second_page), 5)
        self.assertTrue(
            all(row["content_format"] == "full_length" for row in full_length_only)
        )

    async def test_library_can_be_sorted_by_user_then_tmdb_rating(self) -> None:
        entries = (
            (101, "Мой фаворит", 7.0, 10),
            (102, "Второе место", 9.5, 8),
            (103, "Без моей оценки", 9.9, None),
        )
        for tmdb_id, title, tmdb_rating, user_rating in entries:
            media_id = await upsert_media(
                tmdb_id=tmdb_id,
                content_format="full_length",
                content_type="movie",
                title=title,
                rating=tmdb_rating,
                database_url=self.database_url,
            )
            await save_user_media(
                user_id=123,
                media_id=media_id,
                status="completed",
                user_rating=user_rating,
                database_url=self.database_url,
            )

        filters = await get_user_library_filters(123, database_url=self.database_url)
        rows = await list_user_library(
            123,
            filters,
            sort_order="rating",
            database_url=self.database_url,
        )

        self.assertEqual(
            [row["title"] for row in rows],
            ["Мой фаворит", "Второе место", "Без моей оценки"],
        )

        with self.assertRaisesRegex(ValueError, "sort order"):
            await list_user_library(
                123,
                filters,
                sort_order="unknown",
                database_url=self.database_url,
            )

    async def test_library_item_belongs_to_requested_user(self) -> None:
        media_id = await upsert_media(
            tmdb_id=42,
            content_format="full_length",
            content_type="movie",
            title="Private title",
            database_url=self.database_url,
        )
        await save_user_media(
            user_id=123,
            media_id=media_id,
            status="completed",
            database_url=self.database_url,
        )

        own_item = await get_user_library_item(
            123,
            media_id,
            database_url=self.database_url,
        )
        other_item = await get_user_library_item(
            456,
            media_id,
            database_url=self.database_url,
        )

        self.assertEqual(own_item["title"], "Private title")
        self.assertIsNone(other_item)

    async def test_deleting_media_cascades_to_user_progress(self) -> None:
        media_id = await upsert_media(
            tmdb_id=42,
            content_format="series",
            content_type="movie",
            title="TV",
            database_url=self.database_url,
        )
        await save_user_media(
            user_id=123,
            media_id=media_id,
            status="planned",
            database_url=self.database_url,
        )

        async with connection_scope(self.database_url) as connection:
            await connection.execute("DELETE FROM media WHERE id = ?", (media_id,))

        self.assertIsNone(
            await get_user_media(123, media_id, database_url=self.database_url)
        )

    async def test_season_progress_is_inserted_and_updated(self) -> None:
        media_id = await upsert_media(
            tmdb_id=42,
            content_format="series",
            content_type="movie",
            title="TV",
            database_url=self.database_url,
        )
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

    async def test_deleting_user_media_cascades_to_season_progress(self) -> None:
        media_id = await upsert_media(
            tmdb_id=42,
            content_format="series",
            content_type="movie",
            title="TV",
            database_url=self.database_url,
        )
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
        media_id = await upsert_media(
            tmdb_id=42,
            content_format="series",
            content_type="movie",
            title="TV",
            database_url=self.database_url,
        )

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
        media_id = await upsert_media(
            tmdb_id=42,
            content_format="series",
            content_type="movie",
            title="TV",
            database_url=self.database_url,
        )
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
        media_id = await upsert_media(
            tmdb_id=42,
            content_format="series",
            content_type="movie",
            title="TV",
            number_of_seasons=2,
            number_of_episodes=10,
            database_url=self.database_url,
        )
        await save_user_media(
            user_id=123,
            media_id=media_id,
            status="watching",
            episodes_watched=0,
            database_url=self.database_url,
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
        media_id = await upsert_media(
            tmdb_id=42,
            content_format="series",
            content_type="movie",
            title="TV",
            number_of_seasons=1,
            number_of_episodes=10,
            database_url=self.database_url,
        )
        await save_user_media(
            user_id=123,
            media_id=media_id,
            status="watching",
            episodes_watched=0,
            database_url=self.database_url,
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
        media_id = await upsert_media(
            tmdb_id=42,
            content_format="full_length",
            content_type="movie",
            title="Movie",
            database_url=self.database_url,
        )

        with self.assertRaises(ValueError):
            await save_user_series_progress(
                user_id=123,
                media_id=media_id,
                seasons={1: 1},
                total_episodes=10,
                database_url=self.database_url,
            )

    async def test_transaction_rolls_back_on_error(self) -> None:
        with self.assertRaises(RuntimeError):
            async with connection_scope(self.database_url) as connection:
                await connection.execute(
                    """
                    INSERT INTO media (content_format, content_type, title)
                    VALUES (?, ?, ?)
                    """,
                    ("full_length", "movie", "Rolled back"),
                )
                raise RuntimeError("stop")

        async with connection_scope(self.database_url) as connection:
            async with connection.execute(
                "SELECT COUNT(*) FROM media WHERE title = ?",
                ("Rolled back",),
            ) as cursor:
                count = (await cursor.fetchone())[0]

        self.assertEqual(count, 0)

    async def test_invalid_values_are_rejected(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            await upsert_media(
                tmdb_id=1,
                content_format="full_length",
                content_type="book",
                title="Wrong type",
                database_url=self.database_url,
            )

    async def test_direct_connection_can_be_closed(self) -> None:
        connection = await connect_database(self.database_url)
        await connection.close()

    def test_non_sqlite_url_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Only sqlite"):
            database_path("postgresql://localhost/botfunilm")


if __name__ == "__main__":
    unittest.main()
