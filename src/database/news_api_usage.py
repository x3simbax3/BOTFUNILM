"""Daily request budget for TheNewsAPI shared by all worker jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.database.connection import connection_scope


class NewsApiDailyBudgetError(RuntimeError):
    pass


@dataclass(frozen=True)
class NewsApiUsage:
    usage_date: str
    requests: int
    api_limit: int | None
    api_remaining: int | None


async def reserve_news_api_request(
    usage_date: date,
    daily_budget: int,
    *,
    database_url: str | None = None,
) -> None:
    if daily_budget <= 0:
        raise ValueError("daily_budget must be positive")
    date_text = usage_date.isoformat()
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            INSERT OR IGNORE INTO news_api_daily_usage (usage_date)
            VALUES (?)
            """,
            (date_text,),
        )
        cursor = await connection.execute(
            """
            UPDATE news_api_daily_usage
            SET requests = requests + 1, updated_at = CURRENT_TIMESTAMP
            WHERE usage_date = ? AND requests < ?
            """,
            (date_text, daily_budget),
        )
        if cursor.rowcount == 0:
            raise NewsApiDailyBudgetError("Daily news API budget is exhausted")


async def update_news_api_quota(
    usage_date: date,
    *,
    api_limit: int | None,
    api_remaining: int | None,
    database_url: str | None = None,
) -> None:
    if api_limit is not None and api_limit < 0:
        raise ValueError("api_limit must be non-negative")
    if api_remaining is not None and api_remaining < 0:
        raise ValueError("api_remaining must be non-negative")
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            UPDATE news_api_daily_usage
            SET api_limit = COALESCE(?, api_limit),
                api_remaining = COALESCE(?, api_remaining),
                updated_at = CURRENT_TIMESTAMP
            WHERE usage_date = ?
            """,
            (api_limit, api_remaining, usage_date.isoformat()),
        )


async def get_news_api_usage(
    usage_date: date,
    *,
    database_url: str | None = None,
) -> NewsApiUsage:
    date_text = usage_date.isoformat()
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT usage_date, requests, api_limit, api_remaining
            FROM news_api_daily_usage
            WHERE usage_date = ?
            """,
            (date_text,),
        ) as cursor:
            row = await cursor.fetchone()
    if row is None:
        return NewsApiUsage(date_text, 0, None, None)
    return NewsApiUsage(
        usage_date=row["usage_date"],
        requests=row["requests"],
        api_limit=row["api_limit"],
        api_remaining=row["api_remaining"],
    )


__all__ = (
    "NewsApiDailyBudgetError",
    "NewsApiUsage",
    "get_news_api_usage",
    "reserve_news_api_request",
    "update_news_api_quota",
)
