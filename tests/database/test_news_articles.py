from datetime import datetime, timedelta, timezone

from src.database.connection import connection_scope
from src.database.news_articles import (
    claim_news_candidate,
    delete_old_news_articles,
    finish_news_candidate,
    record_news_delivery,
    save_news_candidate,
)
from src.news_models import NewsArticle
from tests.support.database import DatabaseTestCase


class NewsArticlePersistenceTests(DatabaseTestCase):
    def article(self, uuid: str, published_at: str) -> NewsArticle:
        return NewsArticle(
            uuid=uuid,
            title=f"Новость {uuid}",
            description="Полное описание.",
            url=f"https://daily.afisha.ru/cinema/{uuid}/",
            image_url=f"https://img.example/{uuid}.jpg",
            source="daily.afisha.ru",
            published_at=published_at,
        )

    async def test_claims_newest_candidate_once_and_marks_it_sent(self) -> None:
        now = datetime(2026, 8, 5, 10, tzinfo=timezone.utc)
        older = self.article("older", "2026-08-05T08:00:00Z")
        newest = self.article("newest", "2026-08-05T09:00:00Z")
        self.assertTrue(
            await save_news_candidate(older, database_url=self.database_url)
        )
        self.assertTrue(
            await save_news_candidate(newest, database_url=self.database_url)
        )
        self.assertFalse(
            await save_news_candidate(newest, database_url=self.database_url)
        )

        claimed = await claim_news_candidate(
            now - timedelta(hours=36),
            database_url=self.database_url,
        )
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.uuid, "newest")
        await finish_news_candidate(
            claimed.uuid,
            "sent",
            database_url=self.database_url,
        )

        async with connection_scope(self.database_url) as connection:
            async with connection.execute(
                "SELECT status, sent_at FROM news_articles WHERE uuid = ?",
                (claimed.uuid,),
            ) as cursor:
                row = await cursor.fetchone()
        self.assertEqual(row["status"], "sent")
        self.assertIsNotNone(row["sent_at"])

    async def test_records_delivery_once_and_deletes_old_finished_articles(
        self,
    ) -> None:
        article = self.article("old", "2026-05-01T09:00:00Z")
        await save_news_candidate(article, database_url=self.database_url)
        await record_news_delivery(
            article.uuid,
            42,
            "sent",
            database_url=self.database_url,
        )
        await record_news_delivery(
            article.uuid,
            42,
            "sent",
            database_url=self.database_url,
        )
        await finish_news_candidate(
            article.uuid,
            "rejected",
            database_url=self.database_url,
        )
        async with connection_scope(self.database_url) as connection:
            await connection.execute(
                "UPDATE news_articles SET discovered_at = '2026-05-01' WHERE uuid = ?",
                (article.uuid,),
            )

        deleted = await delete_old_news_articles(
            datetime(2026, 8, 1, tzinfo=timezone.utc),
            database_url=self.database_url,
        )

        self.assertEqual(deleted, 1)
        async with connection_scope(self.database_url) as connection:
            async with connection.execute(
                "SELECT COUNT(*) AS count FROM news_article_deliveries"
            ) as cursor:
                row = await cursor.fetchone()
        self.assertEqual(row["count"], 0)
