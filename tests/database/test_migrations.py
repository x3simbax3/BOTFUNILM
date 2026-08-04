import sqlite3

from src.database.connection import connect_database, connection_scope, database_path
from src.database.media import upsert_media
from tests.support.database import DatabaseTestCase


class MigrationTests(DatabaseTestCase):
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
        self.assertIn(("user_media_rating_details", "table"), objects)
        self.assertIn(("user_season_progress", "table"), objects)
        self.assertIn(("media_seasons", "table"), objects)
        self.assertIn(("user_library_filters", "table"), objects)
        self.assertIn(("ix_media_status", "index"), objects)
        self.assertIn(("media_search_terms", "table"), objects)
        self.assertIn(("ix_bot_users_news_recipients", "index"), objects)
        self.assertIn(("ix_bot_users_last_activity", "index"), objects)
        self.assertIn(("ix_media_search_terms_term", "index"), objects)
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

    async def test_connections_enable_wal_and_busy_timeout(self) -> None:
        connection = await connect_database(self.database_url)
        try:
            journal_mode = (
                await (await connection.execute("PRAGMA journal_mode")).fetchone()
            )[0]
            busy_timeout = (
                await (await connection.execute("PRAGMA busy_timeout")).fetchone()
            )[0]
        finally:
            await connection.close()

        self.assertEqual(journal_mode, "wal")
        self.assertGreaterEqual(busy_timeout, 5000)

    def test_non_sqlite_url_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Only sqlite"):
            database_path("postgresql://localhost/botfunilm")
