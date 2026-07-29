from src.database.media import get_media_by_tmdb, update_media_poster, upsert_media
from src.database.media_search import find_media_by_title
from tests.support.database import DatabaseTestCase


class MediaTests(DatabaseTestCase):
    async def test_upsert_media_inserts_and_updates(self) -> None:
        media_id = await self.create_media(
            tmdb_id=42,
            content_format="full_length",
            content_type="movie",
            title="Old title",
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
        expected_id = await self.create_media(
            tmdb_id=42,
            content_format="series",
            content_type="anime",
            title="О моём перерождении в слизь",
            original_title="Tensei Shitara Slime Datta Ken",
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
        await self.create_media(
            tmdb_id=42,
            content_format="full_length",
            content_type="movie",
            title="Матрица",
        )

        row = await find_media_by_title(
            "Матрица",
            "series",
            "movie",
            database_url=self.database_url,
        )

        self.assertIsNone(row)
