"""Fetch, validate, and select cinema news candidates."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from redis.asyncio import Redis

from config.config import (
    NEWS_ALLOWED_DOMAINS,
    NEWS_API_DAILY_BUDGET,
    NEWS_MAX_AGE_HOURS,
    NEWS_RETENTION_DAYS,
)
from src.database.news_api_usage import (
    NewsApiDailyBudgetError,
    reserve_news_api_request,
    update_news_api_quota,
)
from src.database.news_articles import (
    claim_news_candidate,
    delete_old_news_articles,
    finish_news_candidate,
    save_news_candidate,
)
from src.jobs.news_broadcast.models import NEWS_FILTERS, NewsFilter
from src.news_api import (
    NEWS_API_BATCH_SIZE,
    NewsApiAuthenticationError,
    NewsApiError,
    NewsApiRateLimitError,
    TheNewsApiProvider,
)
from src.news_models import NewsArticle, NewsImage
from src.news_provider import NewsProvider

logger = logging.getLogger(__name__)
NEWS_API_MAX_PAGES = 4


async def select_news_article(
    redis: Redis,
    now: datetime,
    *,
    database_url: str | None = None,
    provider: NewsProvider | None = None,
) -> tuple[NewsFilter, NewsArticle, NewsImage] | None:
    _ = redis  # The outer Redis lock serializes manual and scheduled broadcasts.
    provider = provider or TheNewsApiProvider()
    await delete_old_news_articles(
        now - timedelta(days=NEWS_RETENTION_DAYS),
        database_url=database_url,
    )
    published_after = (now - timedelta(hours=NEWS_MAX_AGE_HOURS)).astimezone(
        timezone.utc
    )
    fetch_error: NewsApiError | NewsApiDailyBudgetError | None = None
    try:
        await _refresh_news_candidates(
            now,
            published_after=published_after,
            database_url=database_url,
            provider=provider,
        )
    except (NewsApiAuthenticationError, NewsApiRateLimitError):
        raise
    except (NewsApiError, NewsApiDailyBudgetError) as exc:
        fetch_error = exc
        logger.warning("News fetch failed; trying cached candidates: error=%s", exc)

    for _ in range(20):
        article = await claim_news_candidate(
            published_after,
            database_url=database_url,
        )
        if article is None:
            if fetch_error is not None:
                raise fetch_error
            return None
        rejection = _article_rejection_reason(article, now)
        if rejection:
            await finish_news_candidate(
                article.uuid,
                "rejected",
                rejection_reason=rejection,
                database_url=database_url,
            )
            continue
        image = await provider.fetch_image(article.image_url or "")
        if image is None:
            await finish_news_candidate(
                article.uuid,
                "rejected",
                rejection_reason="invalid-image",
                database_url=database_url,
            )
            logger.info(
                "News candidate rejected: uuid=%s source=%s reason=invalid-image",
                article.uuid,
                article.source,
            )
            continue
        return NEWS_FILTERS[0], article, image
    if fetch_error is not None:
        raise fetch_error
    return None


async def _refresh_news_candidates(
    now: datetime,
    *,
    published_after: datetime,
    database_url: str | None,
    provider: NewsProvider,
) -> None:
    async def reserve_request() -> None:
        await reserve_news_api_request(
            now.date(),
            NEWS_API_DAILY_BUDGET,
            database_url=database_url,
        )

    for page in range(1, NEWS_API_MAX_PAGES + 1):
        result = await provider.fetch_news(
            published_after=published_after,
            page=page,
            before_request=reserve_request,
        )
        await update_news_api_quota(
            now.date(),
            api_limit=result.api_limit,
            api_remaining=result.api_remaining,
            database_url=database_url,
        )

        articles = sorted(
            result.articles,
            key=lambda article: (
                _published_at(article) or datetime.min.replace(tzinfo=timezone.utc)
            ),
            reverse=True,
        )
        saved_candidate = False
        for article in articles:
            rejection = _article_rejection_reason(article, now)
            if rejection == "truncated-description":
                complete_description = await provider.fetch_description(article.url)
                if complete_description:
                    article = replace(article, description=complete_description)
                    rejection = _article_rejection_reason(article, now)
            if rejection:
                logger.info(
                    "News candidate rejected: uuid=%s source=%s reason=%s",
                    article.uuid,
                    article.source,
                    rejection,
                )
                continue
            saved_candidate = (
                await save_news_candidate(article, database_url=database_url)
                or saved_candidate
            )

        if saved_candidate or len(result.articles) < NEWS_API_BATCH_SIZE:
            break


def _article_rejection_reason(article: NewsArticle, now: datetime) -> str | None:
    published_at = _published_at(article)
    utc_now = now.astimezone(timezone.utc)
    if published_at is None:
        return "invalid-published-at"
    if published_at > utc_now + timedelta(minutes=10):
        return "future-published-at"
    if published_at < utc_now - timedelta(hours=NEWS_MAX_AGE_HOURS):
        return "stale"
    url_hostname = urlsplit(article.url).hostname or ""
    if not any(
        url_hostname == domain or url_hostname.endswith(f".{domain}")
        for domain in NEWS_ALLOWED_DOMAINS
    ):
        return "untrusted-source"
    if not article.description:
        return "missing-description"
    if article.description.endswith(("...", "…")):
        return "truncated-description"
    if not article.image_url:
        return "missing-image"
    if "favicon" in urlsplit(article.image_url).path.lower():
        return "favicon-image"
    return None


def _published_at(article: NewsArticle) -> datetime | None:
    try:
        value = datetime.fromisoformat(article.published_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc)


__all__ = ("select_news_article",)
