import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch, sentinel

from src.database.media import get_media_by_tmdb
from src.services import completed_movie
from tests.support.database import DatabaseTestCase


@asynccontextmanager
async def connection_scope_stub(*args, **kwargs):
    yield sentinel.connection


class CompletedMovieServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_unreleased_movie(self) -> None:
        with self.assertRaises(completed_movie.UnreleasedMediaError):
            await completed_movie.save_completed_movie(
                123,
                {
                    "tmdb_id": 42,
                    "tmdb_title": "Будущий фильм",
                    "content_type": "movie",
                    "is_released": False,
                },
                8.0,
            )

    async def test_saves_catalogue_and_user_entry_on_same_connection(self) -> None:
        workflow_data = {
            "tmdb_id": 42,
            "tmdb_title": "Фильм",
            "content_type": "cartoon",
            "ratings": {"story": 9},
        }
        with (
            patch.object(
                completed_movie,
                "ensure_media",
                AsyncMock(return_value=7),
            ) as ensure,
            patch.object(completed_movie, "save_user_media", AsyncMock()) as save,
            patch.object(
                completed_movie,
                "connection_scope",
                connection_scope_stub,
            ),
        ):
            media_id = await completed_movie.save_completed_movie(
                123,
                workflow_data,
                8.6,
            )

        ensure.assert_awaited_once_with(
            workflow_data,
            "full_length",
            connection=sentinel.connection,
        )
        save.assert_awaited_once_with(
            user_id=123,
            media_id=7,
            status="completed",
            user_rating=9,
            rating_details={"story": 9},
            connection=sentinel.connection,
        )
        self.assertEqual(media_id, 7)


class CompletedMovieTransactionTests(DatabaseTestCase):
    async def test_user_write_failure_rolls_back_new_catalogue_entry(self) -> None:
        workflow_data = {
            "tmdb_id": 42,
            "tmdb_title": "Фильм",
            "content_type": "movie",
        }
        with patch.object(
            completed_movie,
            "save_user_media",
            AsyncMock(side_effect=RuntimeError("forced failure")),
        ):
            with self.assertRaisesRegex(RuntimeError, "forced failure"):
                await completed_movie.save_completed_movie(
                    123,
                    workflow_data,
                    8.0,
                    database_url=self.database_url,
                )

        media = await get_media_by_tmdb(
            42,
            "full_length",
            "movie",
            database_url=self.database_url,
        )
        self.assertIsNone(media)


if __name__ == "__main__":
    unittest.main()
