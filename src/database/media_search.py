"""Fuzzy lookup in the local media catalogue."""

import aiosqlite

from src.database.connection import connection_scope
from src.tmdb_matching import MIN_RELEVANCE, title_relevance_score


async def find_media_by_title(
    title: str,
    content_format: str,
    content_type: str,
    *,
    database_url: str | None = None,
) -> aiosqlite.Row | None:
    """Return the closest local title using the shared matching rules."""
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT id, title, original_title
            FROM media
            WHERE content_format = ? AND content_type = ?
            """,
            (content_format, content_type),
        ) as cursor:
            rows = await cursor.fetchall()

        best = None
        best_score = 0.0
        for row in rows:
            score = title_relevance_score(dict(row), title)
            if score > best_score:
                best = row
                best_score = score

        if best is None or best_score < MIN_RELEVANCE:
            return None

        async with connection.execute(
            "SELECT * FROM media WHERE id = ?",
            (best["id"],),
        ) as cursor:
            return await cursor.fetchone()


__all__ = ("find_media_by_title",)
