import asyncio
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from src import news_api
from src.news_api import (
    NewsApiError,
    NewsApiRateLimitError,
    NewsApiUnavailableError,
    _MetaDescriptionParser,
    _parse_article,
    fetch_news,
)


class NewsApiParsingTests(unittest.TestCase):
    def test_parses_article_and_decodes_source(self) -> None:
        article = _parse_article(
            {
                "uuid": "article-id",
                "title": "Заголовок",
                "description": None,
                "snippet": "Короткое описание",
                "url": "https://example.com/article",
                "image_url": "https://cdn.example.com/poster.jpg",
                "source": "example.com%20%20",
                "published_at": "2026-07-30T10:00:00Z",
            }
        )

        self.assertIsNotNone(article)
        self.assertEqual(article.description, "")
        self.assertEqual(article.source, "example.com")

    def test_prefers_complete_open_graph_description(self) -> None:
        parser = _MetaDescriptionParser()
        parser.feed(
            '<meta name="description" content="Обычное описание">'
            '<meta property="og:description" content="Полное описание новости">'
        )

        self.assertEqual(parser.description, "Полное описание новости")

    def test_rejects_unsafe_article_url_and_ignores_unsafe_image(self) -> None:
        self.assertIsNone(
            _parse_article(
                {
                    "uuid": "bad",
                    "title": "Заголовок",
                    "url": "javascript:alert(1)",
                }
            )
        )
        article = _parse_article(
            {
                "uuid": "safe",
                "title": "Заголовок",
                "url": "https://example.com/article",
                "image_url": "https://user:password@example.com/poster.jpg",
            }
        )
        self.assertIsNotNone(article)
        self.assertIsNone(article.image_url)


class NewsApiRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetches_all_news_with_quota_and_optional_images(self) -> None:
        response = SimpleNamespace(
            status=200,
            headers={"X-UsageLimit-Limit": "100", "X-UsageLimit-Remaining": "93"},
        )
        request_context = MagicMock()
        request_context.__aenter__ = AsyncMock(return_value=response)
        request_context.__aexit__ = AsyncMock(return_value=None)
        session = MagicMock()
        session.get.return_value = request_context
        payload = {
            "data": [
                {
                    "uuid": "with-image",
                    "title": "С фото",
                    "url": "https://example.com/with-image",
                    "image_url": "https://example.com/image.jpg",
                },
                {
                    "uuid": "without-image",
                    "title": "Без фото",
                    "url": "https://example.com/without-image",
                    "image_url": None,
                },
            ]
        }

        with (
            patch.object(news_api, "THENEWSAPI_KEY", "token"),
            patch.object(
                news_api,
                "get_http_session",
                new=AsyncMock(return_value=session),
            ),
            patch.object(
                news_api,
                "_read_response",
                new=AsyncMock(return_value=payload),
            ),
        ):
            result = await fetch_news(
                published_after=datetime(2026, 7, 28, tzinfo=timezone.utc)
            )

        self.assertEqual(
            [article.uuid for article in result.articles],
            ["with-image", "without-image"],
        )
        self.assertEqual((result.api_limit, result.api_remaining), (100, 93))
        url = session.get.call_args.args[0]
        params = session.get.call_args.kwargs["params"]
        self.assertEqual(url, "https://api.thenewsapi.com/v1/news/all")
        self.assertEqual(params["published_after"], "2026-07-28T00:00:00")
        self.assertEqual(params["sort"], "published_at")
        self.assertIn("daily.afisha.ru", params["domains"])
        self.assertEqual(session.get.call_count, 1)

    async def test_daily_usage_limit_is_reported_as_rate_limit(self) -> None:
        response = SimpleNamespace(status=402)
        request_context = MagicMock()
        request_context.__aenter__ = AsyncMock(return_value=response)
        request_context.__aexit__ = AsyncMock(return_value=None)
        session = MagicMock()
        session.get.return_value = request_context

        with (
            patch.object(news_api, "THENEWSAPI_KEY", "token"),
            patch.object(
                news_api,
                "get_http_session",
                new=AsyncMock(return_value=session),
            ),
            patch.object(
                news_api,
                "_read_response",
                new=AsyncMock(
                    return_value={"error": {"message": "Daily limit reached"}}
                ),
            ),
        ):
            with self.assertRaisesRegex(NewsApiRateLimitError, "Daily limit"):
                await fetch_news(
                    published_after=datetime(2026, 7, 28, tzinfo=timezone.utc)
                )

    async def test_retries_python_310_asyncio_timeout(self) -> None:
        request_context = MagicMock()
        request_context.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError)
        request_context.__aexit__ = AsyncMock(return_value=None)
        session = MagicMock()
        session.get.return_value = request_context
        before_request = AsyncMock()

        with (
            patch.object(news_api, "THENEWSAPI_KEY", "token"),
            patch.object(news_api, "NEWS_API_RETRIES", 2),
            patch.object(
                news_api,
                "get_http_session",
                new=AsyncMock(return_value=session),
            ),
            patch.object(news_api.asyncio, "sleep", new=AsyncMock()),
        ):
            with self.assertRaises(NewsApiUnavailableError):
                await fetch_news(
                    published_after=datetime(2026, 7, 28, tzinfo=timezone.utc),
                    before_request=before_request,
                )

        self.assertEqual(session.get.call_count, 2)
        self.assertEqual(before_request.await_count, 2)

    async def test_retries_non_json_server_error(self) -> None:
        response = SimpleNamespace(status=502, headers={})
        request_context = MagicMock()
        request_context.__aenter__ = AsyncMock(return_value=response)
        request_context.__aexit__ = AsyncMock(return_value=None)
        session = MagicMock()
        session.get.return_value = request_context

        with (
            patch.object(news_api, "THENEWSAPI_KEY", "token"),
            patch.object(news_api, "NEWS_API_RETRIES", 2),
            patch.object(
                news_api,
                "get_http_session",
                new=AsyncMock(return_value=session),
            ),
            patch.object(
                news_api,
                "_read_response",
                new=AsyncMock(side_effect=NewsApiError("invalid JSON")),
            ),
            patch.object(news_api.asyncio, "sleep", new=AsyncMock()),
        ):
            with self.assertRaises(NewsApiUnavailableError):
                await fetch_news(
                    published_after=datetime(2026, 7, 28, tzinfo=timezone.utc)
                )

        self.assertEqual(session.get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
