import asyncio
import unittest
from unittest.mock import patch

import aiohttp

from src import tmdb_client, tmdb_search
from src.tmdb_matching import make_queries, normalize_text
from src.tmdb_models import (
    TmdbAuthenticationError,
    TmdbError,
    TmdbNotConfiguredError,
    TmdbRateLimitError,
    TmdbUnavailableError,
)
from tests.support.tmdb import ResponseStub, SessionStub, mock_tmdb_api


class TmdbSearchTests(unittest.IsolatedAsyncioTestCase):
    def test_make_queries_returns_original_first(self) -> None:
        queries = make_queries("О моем перерождении в слизь")
        self.assertEqual(queries[0], "О моем перерождении в слизь")

    def test_make_queries_removes_stop_words(self) -> None:
        queries = make_queries("О моем перерождении в слизь")
        self.assertIn("моем перерождении слизь", queries)

    def test_make_queries_keeps_long_words(self) -> None:
        queries = make_queries("Токийский гуль")
        self.assertIn("Токийский гуль", queries)

    def test_make_queries_deduplicates(self) -> None:
        queries = make_queries("Аниме")
        # "Аниме" без стоп-слов = "Аниме" (дубликат)
        normalized = [normalize_text(q) for q in queries]
        self.assertEqual(len(normalized), len(set(normalized)))

    # --- _relevance_score ---

    async def test_empty_query_raises(self) -> None:
        with self.assertRaises(ValueError):
            await tmdb_search.find_title_guess("", "full_length", "movie")

    async def test_no_api_key_raises(self) -> None:
        with patch.object(tmdb_search, "TMDB_API", ""):
            with self.assertRaises(TmdbNotConfiguredError):
                await tmdb_search.find_title_guess("test", "full_length", "movie")

    async def test_search_uses_specific_endpoint_and_original_title_score(self) -> None:
        data = {
            "results": [
                {
                    "id": 42,
                    "title": "Локальное название",
                    "original_title": "Original Match",
                    "genre_ids": [18],
                }
            ]
        }
        with mock_tmdb_api(data) as fetch:
            result = await tmdb_search.find_title_guess(
                "Original Match",
                "full_length",
                "movie",
            )

        self.assertEqual(result.tmdb_id, 42)
        self.assertEqual(
            fetch.await_args.args[1], f"{tmdb_search.TMDB_URL}/search/movie"
        )
        self.assertNotIn("with_genres", fetch.await_args.args[2])

    async def test_fetch_json_classifies_http_errors(self) -> None:
        cases = (
            (401, TmdbAuthenticationError),
            (403, TmdbAuthenticationError),
            (429, TmdbRateLimitError),
            (500, TmdbUnavailableError),
            (422, TmdbError),
        )

        for status, error_type in cases:
            with self.subTest(status=status):
                headers = {"Retry-After": "0"} if status == 429 else None
                session = SessionStub(ResponseStub(status, headers=headers))
                with self.assertRaises(error_type):
                    await tmdb_client.fetch_json(
                        session,
                        "https://api.themoviedb.org/3/test",
                        {},
                        "token",
                    )
                self.assertEqual(session.call_count, 2 if status == 429 else 1)
                self.assertFalse(session.last_get_kwargs["allow_redirects"])

    async def test_fetch_json_classifies_timeout_and_network_error(self) -> None:
        for error in (asyncio.TimeoutError(), aiohttp.ClientConnectionError()):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(TmdbUnavailableError):
                    await tmdb_client.fetch_json(
                        SessionStub(error=error),
                        "https://api.themoviedb.org/3/test",
                        {},
                        "token",
                    )

    async def test_fetch_json_rejects_untrusted_host_before_request(self) -> None:
        session = SessionStub(ResponseStub(200, {"ok": True}))

        with self.assertRaises(ValueError):
            await tmdb_client.fetch_json(
                session,
                "https://attacker.example/3/search/movie",
                {},
                "token",
            )

        self.assertEqual(session.call_count, 0)

    async def test_fetch_json_rejects_oversized_response(self) -> None:
        session = SessionStub(ResponseStub(200, raw_body=b'{"value":"large"}'))

        with (
            patch.object(tmdb_client, "TMDB_MAX_RESPONSE_BYTES", 8),
            self.assertRaisesRegex(TmdbError, "too large"),
        ):
            await tmdb_client.fetch_json(
                session,
                "https://api.themoviedb.org/3/test",
                {},
                "token",
            )
