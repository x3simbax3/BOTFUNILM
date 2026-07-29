import unittest
from unittest.mock import AsyncMock, patch

from src.services import title_search
from src.tmdb_models import TmdbTitle


class TitleSearchServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_match_skips_remote_search_and_updates_cached_poster(
        self,
    ) -> None:
        local = {
            "id": 7,
            "tmdb_id": 42,
            "title": "Матрица",
            "description": "Описание",
            "poster_path": "/poster.jpg",
            "rating": 8.7,
            "original_title": "The Matrix",
            "first_air_date": None,
            "release_date": "1999-03-31",
        }
        remote_started = AsyncMock()
        with (
            patch.object(
                title_search,
                "find_media_by_title",
                AsyncMock(return_value=local),
            ),
            patch.object(
                title_search,
                "download_poster",
                AsyncMock(return_value="media/posters/matrix.jpg"),
            ) as download,
            patch.object(
                title_search,
                "update_media_poster",
                AsyncMock(),
            ) as update,
            patch.object(
                title_search,
                "find_title_candidates",
                AsyncMock(),
            ) as remote,
        ):
            candidates = await title_search.search_title_candidates(
                "матрица",
                "full_length",
                "movie",
                remote_search_started=remote_started,
            )

        remote.assert_not_awaited()
        remote_started.assert_not_awaited()
        download.assert_awaited_once()
        update.assert_awaited_once_with(7, "media/posters/matrix.jpg")
        self.assertEqual(candidates[0].media_id, 7)
        self.assertEqual(candidates[0].poster_path, "media/posters/matrix.jpg")

    async def test_remote_search_reports_transition_and_maps_candidates(self) -> None:
        remote_started = AsyncMock()
        title = TmdbTitle(
            title="Матрица",
            overview=None,
            poster_url=None,
            original_query="матрица",
            normalized_query="матрица",
            tmdb_id=42,
        )
        with (
            patch.object(
                title_search,
                "find_media_by_title",
                AsyncMock(return_value=None),
            ),
            patch.object(
                title_search,
                "find_title_candidates",
                AsyncMock(return_value=[title]),
            ) as remote,
        ):
            candidates = await title_search.search_title_candidates(
                "матрица",
                "full_length",
                "movie",
                remote_search_started=remote_started,
            )

        remote_started.assert_awaited_once_with()
        remote.assert_awaited_once_with(
            "матрица",
            "full_length",
            "movie",
            limit=title_search.MAX_TITLE_CANDIDATES,
        )
        self.assertEqual(candidates[0].tmdb_id, 42)
        self.assertIsNone(candidates[0].media_id)


if __name__ == "__main__":
    unittest.main()
