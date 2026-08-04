from src.database.connection import connection_scope
from src.database.media import get_media_by_tmdb
from src.database.user_media import (
    delete_user_media,
    get_user_media,
    save_user_media,
    set_user_media_status,
    update_user_media_badge,
    update_user_media_rating,
)
from tests.support.database import DatabaseTestCase


class UserMediaTests(DatabaseTestCase):
    async def test_dropped_status_is_not_supported(self) -> None:
        media_id = await self.create_user_media(status="watching")

        with self.assertRaises(ValueError):
            await set_user_media_status(
                123,
                media_id,
                "dropped",
                database_url=self.database_url,
            )

    async def test_badge_can_be_set_and_removed(self) -> None:
        media_id = await self.create_user_media(status="completed")

        self.assertTrue(
            await update_user_media_badge(
                123,
                media_id,
                "top",
                database_url=self.database_url,
            )
        )
        row = await get_user_media(123, media_id, database_url=self.database_url)
        self.assertEqual(row["badge"], "top")

        self.assertTrue(
            await update_user_media_badge(
                123,
                media_id,
                None,
                database_url=self.database_url,
            )
        )
        row = await get_user_media(123, media_id, database_url=self.database_url)
        self.assertIsNone(row["badge"])

        with self.assertRaises(ValueError):
            await update_user_media_badge(
                123,
                media_id,
                "unknown",
                database_url=self.database_url,
            )

    async def test_user_media_is_inserted_and_updated(self) -> None:
        media_id = await self.create_media(
            tmdb_id=42,
            content_format="series",
            content_type="anime",
            title="Anime",
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
        media_id = await self.create_media(
            tmdb_id=44,
            content_format="full_length",
            content_type="movie",
            title="Popular movie",
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
        media_id = await self.create_media(
            tmdb_id=43,
            content_format="full_length",
            content_type="movie",
            title="Planned movie",
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

    async def test_deleting_media_cascades_to_user_progress(self) -> None:
        media_id = await self.create_media(
            tmdb_id=42,
            content_format="series",
            content_type="movie",
            title="TV",
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
