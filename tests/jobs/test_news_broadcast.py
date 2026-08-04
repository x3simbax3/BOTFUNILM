import html
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from aiogram.exceptions import TelegramBadRequest

from src.database.connection import connection_scope
from src.jobs.news_broadcast import (
    NEWS_FILTERS,
    select_news_article,
    send_news_broadcast,
)
from src.news_api import NewsArticle
from tests.support.database import DatabaseTestCase


class NewsBroadcastTests(DatabaseTestCase):
    timezone = ZoneInfo("Europe/Moscow")

    def article(self, uuid: str = "fresh") -> NewsArticle:
        return NewsArticle(
            uuid=uuid,
            title="Новый <фильм>",
            description="Описание & подробности",
            url="https://example.com/news",
            image_url="https://example.com/poster.jpg",
            source="example.com",
            published_at="2026-07-30T10:00:00Z",
        )

    async def test_skips_sent_uuid_and_claims_next_article(self) -> None:
        redis = AsyncMock()
        redis.get.return_value = None
        redis.zadd.side_effect = [0, 1]
        articles = [self.article("sent"), self.article("fresh")]

        with patch(
            "src.jobs.news_broadcast.fetch_news",
            new=AsyncMock(return_value=articles),
        ):
            selected = await select_news_article(
                redis,
                datetime(2026, 7, 30, 12, tzinfo=self.timezone),
            )

        self.assertIsNotNone(selected)
        self.assertEqual(selected[1].uuid, "fresh")
        self.assertEqual(redis.zadd.await_count, 2)
        redis.zremrangebyscore.assert_awaited_once()
        redis.expire.assert_awaited_once()
        redis.set.assert_awaited_once()

    async def test_skips_article_without_image(self) -> None:
        redis = AsyncMock()
        redis.get.return_value = None
        redis.zadd.return_value = 1
        articles = [
            NewsArticle(**{**self.article("no-image").__dict__, "image_url": None}),
            self.article("with-image"),
        ]

        with patch(
            "src.jobs.news_broadcast.fetch_news",
            new=AsyncMock(return_value=articles),
        ):
            selected = await select_news_article(
                redis,
                datetime(2026, 7, 30, 12, tzinfo=self.timezone),
            )

        self.assertIsNotNone(selected)
        self.assertEqual(selected[1].uuid, "with-image")
        redis.zadd.assert_awaited_once()

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
        telegram_message = SimpleNamespace(
            photo=[SimpleNamespace(file_id="telegram-file-id")]
        )
        bot = AsyncMock()
        bot.send_photo.return_value = telegram_message

        with (
            patch(
                "src.jobs.news_broadcast.select_news_article",
                new=AsyncMock(return_value=(article_filter, article)),
            ),
            patch("src.jobs.news_broadcast.asyncio.sleep", new=AsyncMock()),
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
            bot.send_photo.await_args_list[0].kwargs["photo"],
            article.image_url,
        )
        self.assertEqual(
            bot.send_photo.await_args_list[1].kwargs["photo"],
            "telegram-file-id",
        )
        bot.send_message.assert_not_awaited()
        self.assertIn("&lt;фильм&gt;", bot.send_photo.await_args.kwargs["caption"])
        self.assertNotIn("Новости ·", bot.send_photo.await_args.kwargs["caption"])

    async def test_expands_truncated_api_description_and_fits_photo_caption(
        self,
    ) -> None:
        async with connection_scope(self.database_url) as connection:
            await connection.execute("INSERT INTO bot_users (user_id) VALUES (1)")
        article = NewsArticle(
            **{
                **self.article().__dict__,
                "description": "Короткое описание...",
            }
        )
        expanded = "Подробный текст новости. " * 100
        bot = AsyncMock()
        bot.send_photo.return_value = SimpleNamespace(photo=[])

        with (
            patch(
                "src.jobs.news_broadcast.select_news_article",
                new=AsyncMock(return_value=(NEWS_FILTERS[2], article)),
            ),
            patch(
                "src.jobs.news_broadcast.fetch_article_text",
                new=AsyncMock(return_value=expanded),
            ),
            patch("src.jobs.news_broadcast.asyncio.sleep", new=AsyncMock()),
        ):
            await send_news_broadcast(
                AsyncMock(),
                bot,
                datetime(2026, 7, 30, 12, tzinfo=self.timezone),
                database_url=self.database_url,
            )

        caption = bot.send_photo.await_args.kwargs["caption"]
        self.assertIn("Подробный текст новости", caption)
        self.assertNotIn("Новости ·", caption)
        visible_caption = html.unescape(caption.replace("<b>", "").replace("</b>", ""))
        self.assertLessEqual(len(visible_caption), 1024)

    async def test_does_not_fall_back_to_text_when_image_is_rejected(self) -> None:
        async with connection_scope(self.database_url) as connection:
            await connection.execute("INSERT INTO bot_users (user_id) VALUES (1)")
        bot = AsyncMock()
        bot.send_photo.side_effect = TelegramBadRequest(
            method=AsyncMock(),
            message="failed to get HTTP URL content",
        )

        with (
            patch(
                "src.jobs.news_broadcast.select_news_article",
                new=AsyncMock(return_value=(NEWS_FILTERS[0], self.article())),
            ),
            patch("src.jobs.news_broadcast.asyncio.sleep", new=AsyncMock()),
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
