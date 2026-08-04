from datetime import date

from src.database.news_api_usage import (
    NewsApiDailyBudgetError,
    get_news_api_usage,
    reserve_news_api_request,
    update_news_api_quota,
)
from tests.support.database import DatabaseTestCase


class NewsApiUsageTests(DatabaseTestCase):
    async def test_enforces_daily_budget_and_stores_api_quota(self) -> None:
        today = date(2026, 8, 4)
        await reserve_news_api_request(today, 2, database_url=self.database_url)
        await reserve_news_api_request(today, 2, database_url=self.database_url)

        with self.assertRaises(NewsApiDailyBudgetError):
            await reserve_news_api_request(today, 2, database_url=self.database_url)

        await update_news_api_quota(
            today,
            api_limit=100,
            api_remaining=98,
            database_url=self.database_url,
        )
        usage = await get_news_api_usage(today, database_url=self.database_url)
        self.assertEqual(
            (usage.requests, usage.api_limit, usage.api_remaining), (2, 100, 98)
        )
