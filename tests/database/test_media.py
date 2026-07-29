from unittest.mock import patch

from src.database import media_search
from src.database.connection import connection_scope
from src.database.media import get_media_by_tmdb, update_media_poster, upsert_media
from src.database.media_search import (
    LOCAL_SEARCH_CANDIDATE_LIMIT,
    backfill_media_search_index,
    find_media_by_title,
)
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

    async def test_partial_upsert_preserves_existing_optional_metadata(self) -> None:
        media_id = await upsert_media(
            tmdb_id=42,
            content_format="series",
            content_type="movie",
            title="Old title",
            original_title="Original title",
            description="Good description",
            poster_path="posters/good.jpg",
            telegram_poster_file_id="telegram-file-id",
            rating=8.5,
            release_date="2025-01-01",
            first_air_date="2025-02-01",
            number_of_seasons=3,
            number_of_episodes=24,
            available_episode_count=20,
            status="Returning Series",
            database_url=self.database_url,
        )

        updated_id = await upsert_media(
            tmdb_id=42,
            content_format="series",
            content_type="movie",
            title="New title",
            database_url=self.database_url,
        )
        row = await get_media_by_tmdb(
            42,
            "series",
            "movie",
            database_url=self.database_url,
        )

        self.assertEqual(updated_id, media_id)
        self.assertEqual(row["title"], "New title")
        self.assertEqual(row["original_title"], "Original title")
        self.assertEqual(row["description"], "Good description")
        self.assertEqual(row["poster_path"], "posters/good.jpg")
        self.assertEqual(row["telegram_poster_file_id"], "telegram-file-id")
        self.assertEqual(row["rating"], 8.5)
        self.assertEqual(row["release_date"], "2025-01-01")
        self.assertEqual(row["first_air_date"], "2025-02-01")
        self.assertEqual(row["number_of_seasons"], 3)
        self.assertEqual(row["number_of_episodes"], 24)
        self.assertEqual(row["available_episode_count"], 20)
        self.assertEqual(row["status"], "Returning Series")

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

    async def test_find_media_by_title_matches_typo_at_start(self) -> None:
        expected_id = await self.create_media(
            tmdb_id=43,
            content_format="full_length",
            content_type="movie",
            title="Матрица",
        )

        row = await find_media_by_title(
            "Натрица",
            "full_length",
            "movie",
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

    async def test_local_fuzzy_search_scores_only_bounded_candidates(self) -> None:
        async with connection_scope(self.database_url) as connection:
            await connection.executemany(
                """
                INSERT INTO media (
                    tmdb_id, content_format, content_type, title,
                    normalized_title
                ) VALUES (?, 'full_length', 'movie', ?, ?)
                """,
                [
                    (index, f"abcdefgh title {index}", f"abcdefgh title {index}")
                    for index in range(150)
                ],
            )
        await backfill_media_search_index(database_url=self.database_url)

        with patch.object(
            media_search,
            "title_relevance_score",
            wraps=media_search.title_relevance_score,
        ) as score:
            await find_media_by_title(
                "abcdefgh typo",
                "full_length",
                "movie",
                database_url=self.database_url,
            )

        self.assertLessEqual(score.call_count, LOCAL_SEARCH_CANDIDATE_LIMIT)
        self.assertGreater(score.call_count, 0)

    async def test_search_index_backfill_handles_preexisting_rows(self) -> None:
        async with connection_scope(self.database_url) as connection:
            await connection.execute(
                """
                INSERT INTO media (
                    tmdb_id, content_format, content_type, title
                ) VALUES (99, 'full_length', 'movie', 'Матрица')
                """
            )

        self.assertEqual(
            await backfill_media_search_index(database_url=self.database_url),
            1,
        )
        row = await find_media_by_title(
            "матрица",
            "full_length",
            "movie",
            database_url=self.database_url,
        )

        self.assertIsNotNone(row)
        self.assertEqual(row["tmdb_id"], 99)
