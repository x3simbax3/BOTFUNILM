"""Persistent inbox and delivery state for cinema news articles."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.database.connection import connection_scope
from src.news_models import NewsArticle


async def save_news_candidate(
    article: NewsArticle,
    *,
    database_url: str | None = None,
) -> bool:
    if not article.image_url:
        raise ValueError("News candidate must have an image URL")
    async with connection_scope(database_url) as connection:
        cursor = await connection.execute(
            """
            INSERT OR IGNORE INTO news_articles (
                uuid, title, description, url, image_url, source, published_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article.uuid,
                article.title,
                article.description,
                article.url,
                article.image_url,
                article.source,
                article.published_at,
            ),
        )
    return cursor.rowcount == 1


async def claim_news_candidate(
    published_after: datetime,
    *,
    database_url: str | None = None,
) -> NewsArticle | None:
    cutoff = published_after.astimezone(timezone.utc).isoformat()
    stale_selection = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            UPDATE news_articles
            SET status = 'candidate', selected_at = NULL
            WHERE status = 'selected' AND datetime(selected_at) < datetime(?)
            """,
            (stale_selection,),
        )
        async with connection.execute(
            """
            SELECT uuid, title, description, url, image_url, source, published_at
            FROM news_articles
            WHERE status = 'candidate'
              AND datetime(published_at) >= datetime(?)
            ORDER BY datetime(published_at) DESC, discovered_at DESC
            LIMIT 1
            """,
            (cutoff,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        cursor = await connection.execute(
            """
            UPDATE news_articles
            SET status = 'selected', selected_at = CURRENT_TIMESTAMP
            WHERE uuid = ? AND status = 'candidate'
            """,
            (row["uuid"],),
        )
        if cursor.rowcount != 1:
            return None
    return NewsArticle(
        uuid=row["uuid"],
        title=row["title"],
        description=row["description"],
        url=row["url"],
        image_url=row["image_url"],
        source=row["source"],
        published_at=row["published_at"],
    )


async def finish_news_candidate(
    uuid: str,
    status: str,
    *,
    rejection_reason: str | None = None,
    database_url: str | None = None,
) -> None:
    if status not in {"candidate", "sent", "rejected"}:
        raise ValueError("Invalid final news status")
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            UPDATE news_articles
            SET status = ?, rejection_reason = ?, selected_at = NULL,
                sent_at = CASE WHEN ? = 'sent' THEN CURRENT_TIMESTAMP ELSE NULL END
            WHERE uuid = ?
            """,
            (status, rejection_reason, status, uuid),
        )


async def record_news_delivery(
    article_uuid: str,
    user_id: int,
    status: str,
    *,
    database_url: str | None = None,
) -> None:
    if status not in {"sent", "deactivated"}:
        raise ValueError("Invalid news delivery status")
    async with connection_scope(database_url) as connection:
        await connection.execute(
            """
            INSERT OR IGNORE INTO news_article_deliveries (
                article_uuid, user_id, status
            ) VALUES (?, ?, ?)
            """,
            (article_uuid, user_id, status),
        )


async def delete_old_news_articles(
    before: datetime,
    *,
    database_url: str | None = None,
) -> int:
    cutoff = before.astimezone(timezone.utc).isoformat()
    async with connection_scope(database_url) as connection:
        cursor = await connection.execute(
            """
            DELETE FROM news_articles
            WHERE status IN ('sent', 'rejected')
              AND datetime(COALESCE(sent_at, discovered_at)) < datetime(?)
            """,
            (cutoff,),
        )
    return cursor.rowcount


__all__ = (
    "claim_news_candidate",
    "delete_old_news_articles",
    "finish_news_candidate",
    "record_news_delivery",
    "save_news_candidate",
)
