import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.database import (
    connect_database,
    connection_scope,
    get_media_by_tmdb,
    get_user_media,
    get_user_season_progress,
    save_user_series_progress,
    save_user_media,
    upsert_media,
)
from src.database.connection import database_path

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
                objects = {(row["name"], row["type"]) for row in await cursor.fetchall()}

        self.assertIn(("media", "table"), objects)
        self.assertIn(("user_media", "table"), objects)
        self.assertIn(("user_season_progress", "table"), objects)
        self.assertIn(("ix_media_status", "index"), objects)
        self.assertIn(("ix_user_media_media_id", "index"), objects)
        self.assertIn(("ix_user_season_progress_media_id", "index"), objects)

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
