import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from src import news_api
from src.news_api import (
    NewsApiRateLimitError,
    _ArticleBodyParser,
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
        self.assertEqual(article.description, "Короткое описание")
        self.assertEqual(article.source, "example.com")

    def test_extracts_text_from_article_body(self) -> None:
        parser = _ArticleBodyParser()
        parser.feed(
            '<div itemprop="articleBody"><p>Первый <a href="#">абзац</a>.</p>'
            "<script>ignore()</script><p>Второй абзац.</p></div>"
        )

        self.assertEqual(parser.text, "Первый абзац. Второй абзац.")

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
    async def test_fetches_top_news_with_quota_and_optional_images(self) -> None:
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
                "кино",
                published_after=datetime(2026, 7, 28, tzinfo=timezone.utc),
            )

        self.assertEqual(
            [article.uuid for article in result.articles],
            ["with-image", "without-image"],
        )
        self.assertEqual((result.api_limit, result.api_remaining), (100, 93))
        url = session.get.call_args.args[0]
        params = session.get.call_args.kwargs["params"]
        self.assertEqual(url, "https://api.thenewsapi.com/v1/news/top")
        self.assertEqual(params["published_after"], "2026-07-28T00:00:00")
        self.assertNotIn("sort", params)

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
                    "кино",
                    published_after=datetime(2026, 7, 28, tzinfo=timezone.utc),
                )


if __name__ == "__main__":
    unittest.main()
