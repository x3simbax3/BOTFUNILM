import html
import re
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from aiogram.exceptions import TelegramBadRequest

from src.database.connection import connection_scope
from src.database.news_api_usage import get_news_api_usage
from src.database.news_articles import finish_news_candidate, save_news_candidate
from src.jobs.news_broadcast import (
    NEWS_FILTERS,
    _article_text,
    select_news_article,
    send_news_broadcast,
)
from src.news_models import NewsArticle, NewsFetchResult, NewsImage
from tests.support.database import DatabaseTestCase


class NewsBroadcastTests(DatabaseTestCase):
    timezone = ZoneInfo("Europe/Moscow")

    def article(self, uuid: str = "fresh") -> NewsArticle:
        return NewsArticle(
            uuid=uuid,
            title="Новый <фильм>",
            description="Описание & подробности",
            url=f"https://daily.afisha.ru/cinema/{uuid}/",
            image_url="https://example.com/poster.jpg",
            source="daily.afisha.ru",
            published_at="2026-07-30T08:00:00Z",
        )

    def image(self) -> NewsImage:
        return NewsImage(data=b"image-bytes", filename="news.jpg")

    async def test_counts_every_provider_request_attempt(self) -> None:
        now = datetime(2026, 7, 30, 12, tzinfo=self.timezone)

        async def fetch_with_retry(*, published_after, before_request):
            self.assertIsNotNone(published_after)
            await before_request()
            await before_request()
            return NewsFetchResult((), 100, 98)

        with patch(
            "src.news_api.TheNewsApiProvider.fetch_news",
            new=AsyncMock(side_effect=fetch_with_retry),
        ):
            selected = await select_news_article(
                AsyncMock(),
                now,
                database_url=self.database_url,
            )

        usage = await get_news_api_usage(
            now.date(),
            database_url=self.database_url,
        )
        self.assertIsNone(selected)
        self.assertEqual(usage.requests, 2)

    async def test_skips_sent_uuid_and_claims_next_article(self) -> None:
        redis = AsyncMock()
        articles = [self.article("sent"), self.article("fresh")]
        await save_news_candidate(articles[0], database_url=self.database_url)
        await finish_news_candidate(
            articles[0].uuid,
            "sent",
            database_url=self.database_url,
        )

        with (
            patch(
                "src.news_api.TheNewsApiProvider.fetch_news",
                new=AsyncMock(return_value=NewsFetchResult(tuple(articles), 100, 99)),
            ),
            patch(
                "src.news_api.TheNewsApiProvider.fetch_image",
                new=AsyncMock(return_value=self.image()),
            ),
        ):
            selected = await select_news_article(
                redis,
                datetime(2026, 7, 30, 12, tzinfo=self.timezone),
                database_url=self.database_url,
            )

        self.assertIsNotNone(selected)
        self.assertEqual(selected[1].uuid, "fresh")

    async def test_requires_an_image_and_selects_next_article(self) -> None:
        redis = AsyncMock()
        articles = [
            NewsArticle(**{**self.article("no-image").__dict__, "image_url": None}),
            self.article("with-image"),
        ]

        with (
            patch(
                "src.news_api.TheNewsApiProvider.fetch_news",
                new=AsyncMock(return_value=NewsFetchResult(tuple(articles), 100, 99)),
            ),
            patch(
                "src.news_api.TheNewsApiProvider.fetch_image",
                new=AsyncMock(return_value=self.image()),
            ) as fetch_image,
        ):
            selected = await select_news_article(
                redis,
                datetime(2026, 7, 30, 12, tzinfo=self.timezone),
                database_url=self.database_url,
            )

        self.assertIsNotNone(selected)
        self.assertEqual(selected[1].uuid, "with-image")
        fetch_image.assert_awaited_once_with(articles[1].image_url)

    async def test_selects_fourth_article_when_first_three_are_rejected(self) -> None:
        articles = [
            NewsArticle(
                **{
                    **self.article(f"rejected-{index}").__dict__,
                    "description": "",
                }
            )
            for index in range(3)
        ]
        articles.append(self.article("fourth"))

        with (
            patch(
                "src.news_api.TheNewsApiProvider.fetch_news",
                new=AsyncMock(return_value=NewsFetchResult(tuple(articles), 100, 99)),
            ),
            patch(
                "src.news_api.TheNewsApiProvider.fetch_image",
                new=AsyncMock(return_value=self.image()),
            ) as fetch_image,
        ):
            selected = await select_news_article(
                AsyncMock(),
                datetime(2026, 7, 30, 12, tzinfo=self.timezone),
                database_url=self.database_url,
            )

        self.assertIsNotNone(selected)
        self.assertEqual(selected[1].uuid, "fourth")
        fetch_image.assert_awaited_once_with(articles[3].image_url)

    async def test_broadcasts_in_batches_and_reuses_telegram_photo(self) -> None:
        async with connection_scope(self.database_url) as connection:
            await connection.executemany(
                "INSERT INTO bot_users (user_id) VALUES (?)",
                ((user_id,) for user_id in range(1, 102)),
            )
            await connection.execute(
                "UPDATE bot_users SET news_enabled = 0 WHERE user_id = 101"
            )
        article_filter = NEWS_FILTERS[0]
        article = self.article()
        await save_news_candidate(article, database_url=self.database_url)
        telegram_message = SimpleNamespace(
            photo=[SimpleNamespace(file_id="telegram-file-id")]
        )
        bot = AsyncMock()
        bot.send_photo.return_value = telegram_message

        with (
            patch(
                "src.jobs.news_broadcast.select_news_article",
                new=AsyncMock(return_value=(article_filter, article, self.image())),
            ),
            patch("src.jobs.news_broadcast.delivery.asyncio.sleep", new=AsyncMock()),
        ):
            stats = await send_news_broadcast(
                AsyncMock(),
                bot,
                datetime(2026, 7, 30, 12, tzinfo=self.timezone),
                database_url=self.database_url,
            )

        self.assertEqual(stats.selected, 100)
        self.assertEqual(stats.sent, 100)
        self.assertEqual(bot.send_photo.await_count, 100)
        self.assertEqual(
            bot.send_photo.await_args_list[0].kwargs["photo"].filename,
            "news.jpg",
        )
        self.assertEqual(
            bot.send_photo.await_args_list[1].kwargs["photo"],
            "telegram-file-id",
        )
        bot.send_message.assert_not_awaited()
        self.assertIn("&lt;фильм&gt;", bot.send_photo.await_args.kwargs["caption"])
        self.assertNotIn("Новости ·", bot.send_photo.await_args.kwargs["caption"])

    async def test_truncates_caption_only_at_telegram_limit(self) -> None:
        async with connection_scope(self.database_url) as connection:
            await connection.execute("INSERT INTO bot_users (user_id) VALUES (1)")
        article = NewsArticle(**{**self.article().__dict__, "description": "д" * 2000})
        await save_news_candidate(article, database_url=self.database_url)
        bot = AsyncMock()
        bot.send_photo.return_value = SimpleNamespace(
            photo=[SimpleNamespace(file_id="telegram-file-id")]
        )

        with patch(
            "src.jobs.news_broadcast.select_news_article",
            new=AsyncMock(return_value=(NEWS_FILTERS[0], article, self.image())),
        ):
            stats = await send_news_broadcast(
                AsyncMock(),
                bot,
                datetime(2026, 7, 30, 12, tzinfo=self.timezone),
                database_url=self.database_url,
            )

        caption = bot.send_photo.await_args.kwargs["caption"]
        visible_caption = html.unescape(re.sub(r"</?b>", "", caption))
        self.assertEqual(stats.sent, 1)
        self.assertEqual(len(visible_caption), 1024)
        self.assertIn("ддд…\n\ndaily.afisha.ru", visible_caption)

    def test_truncates_caption_when_title_itself_is_too_long(self) -> None:
        article = NewsArticle(
            **{
                **self.article().__dict__,
                "title": "з" * 2000,
                "description": "Описание",
            }
        )

        caption = _article_text(article)
        visible_caption = html.unescape(re.sub(r"</?b>", "", caption))

        self.assertEqual(len(visible_caption), 1024)
        self.assertTrue(visible_caption.startswith("ззз"))
        self.assertTrue(visible_caption.endswith("daily.afisha.ru"))

    async def test_rejects_provider_truncation_instead_of_shortening_caption(
        self,
    ) -> None:
        redis = AsyncMock()
        truncated = NewsArticle(
            **{**self.article().__dict__, "description": "Оборванное описание..."}
        )
        with (
            patch(
                "src.news_api.TheNewsApiProvider.fetch_news",
                new=AsyncMock(return_value=NewsFetchResult((truncated,), 100, 99)),
            ),
            patch(
                "src.news_api.TheNewsApiProvider.fetch_image",
                new=AsyncMock(),
            ) as fetch_image,
            patch(
                "src.news_api.TheNewsApiProvider.fetch_description",
                new=AsyncMock(return_value=None),
            ),
        ):
            selected = await select_news_article(
                redis,
                datetime(2026, 7, 30, 12, tzinfo=self.timezone),
                database_url=self.database_url,
            )

        self.assertIsNone(selected)
        fetch_image.assert_not_awaited()

    async def test_replaces_truncated_api_description_with_complete_metadata(
        self,
    ) -> None:
        redis = AsyncMock()
        truncated = NewsArticle(
            **{**self.article().__dict__, "description": "Оборванное описание..."}
        )
        with (
            patch(
                "src.news_api.TheNewsApiProvider.fetch_news",
                new=AsyncMock(return_value=NewsFetchResult((truncated,), 100, 99)),
            ),
            patch(
                "src.news_api.TheNewsApiProvider.fetch_description",
                new=AsyncMock(return_value="Полное описание без обрезания."),
            ),
            patch(
                "src.news_api.TheNewsApiProvider.fetch_image",
                new=AsyncMock(return_value=self.image()),
            ),
        ):
            selected = await select_news_article(
                redis,
                datetime(2026, 7, 30, 12, tzinfo=self.timezone),
                database_url=self.database_url,
            )

        self.assertIsNotNone(selected)
        self.assertEqual(selected[1].description, "Полное описание без обрезания.")

    async def test_does_not_fall_back_to_text_when_image_is_rejected(self) -> None:
        async with connection_scope(self.database_url) as connection:
            await connection.execute("INSERT INTO bot_users (user_id) VALUES (1)")
        article = self.article()
        await save_news_candidate(article, database_url=self.database_url)
        bot = AsyncMock()
        bot.send_photo.side_effect = TelegramBadRequest(
            method=AsyncMock(),
            message="failed to get HTTP URL content",
        )

        with (
            patch(
                "src.jobs.news_broadcast.select_news_article",
                new=AsyncMock(return_value=(NEWS_FILTERS[0], article, self.image())),
            ),
            patch("src.jobs.news_broadcast.delivery.asyncio.sleep", new=AsyncMock()),
        ):
            stats = await send_news_broadcast(
                AsyncMock(),
                bot,
                datetime(2026, 7, 30, 12, tzinfo=self.timezone),
                database_url=self.database_url,
            )

        self.assertEqual(stats.failed, 1)
        self.assertEqual(stats.sent, 0)
        bot.send_message.assert_not_awaited()
        async with connection_scope(self.database_url) as connection:
            async with connection.execute(
                """
                SELECT selected, sent, failed FROM notification_delivery_runs
                WHERE notification_type = 'news'
                """
            ) as cursor:
                delivery = await cursor.fetchone()
        self.assertEqual(
            (delivery["selected"], delivery["sent"], delivery["failed"]),
            (1, 0, 1),
        )

    async def test_resumes_only_failed_users_after_chat_bad_request(self) -> None:
        async with connection_scope(self.database_url) as connection:
            await connection.executemany(
                "INSERT INTO bot_users (user_id) VALUES (?)",
                ((1,), (2,)),
            )
        article = self.article()
        await save_news_candidate(article, database_url=self.database_url)
        telegram_message = SimpleNamespace(
            photo=[SimpleNamespace(file_id="telegram-file-id")]
        )
        chat_error = TelegramBadRequest(
            method=AsyncMock(),
            message="chat not found",
        )
        first_bot = AsyncMock()
        first_bot.send_photo.side_effect = [chat_error, telegram_message]
        second_bot = AsyncMock()
        second_bot.send_photo.return_value = telegram_message
        selected = (NEWS_FILTERS[0], article, self.image())

        with (
            patch(
                "src.jobs.news_broadcast.select_news_article",
                new=AsyncMock(return_value=selected),
            ),
            patch("src.jobs.news_broadcast.delivery.asyncio.sleep", new=AsyncMock()),
        ):
            first_stats = await send_news_broadcast(
                AsyncMock(),
                first_bot,
                datetime(2026, 7, 30, 12, tzinfo=self.timezone),
                database_url=self.database_url,
            )
            second_stats = await send_news_broadcast(
                AsyncMock(),
                second_bot,
                datetime(2026, 7, 30, 14, tzinfo=self.timezone),
                database_url=self.database_url,
            )

        self.assertEqual((first_stats.sent, first_stats.failed), (1, 1))
        self.assertEqual((second_stats.selected, second_stats.sent), (1, 1))
        self.assertEqual(first_bot.send_photo.await_args_list[1].kwargs["chat_id"], 2)
        self.assertEqual(second_bot.send_photo.await_args.kwargs["chat_id"], 1)
