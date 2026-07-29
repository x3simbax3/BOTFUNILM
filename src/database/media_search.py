"""Bounded fuzzy lookup in the local media catalogue."""

import aiosqlite

from src.database.connection import connection_scope
from src.tmdb_matching import MIN_RELEVANCE, normalize_text, title_relevance_score

LOCAL_SEARCH_CANDIDATE_LIMIT = 100
LOCAL_SEARCH_PREFIX_LENGTH = 8
SEARCH_INDEX_BACKFILL_BATCH_SIZE = 500


async def find_media_by_title(
    title: str,
    content_format: str,
    content_type: str,
    *,
    database_url: str | None = None,
) -> aiosqlite.Row | None:
    """Return the closest match after an indexed, bounded candidate lookup."""
    normalized = normalize_text(title)
    if not normalized:
        return None

    async with connection_scope(database_url) as connection:
        exact = await _find_exact(
            connection,
            normalized,
            content_format,
            content_type,
        )
        if exact is not None:
            return exact

        prefix = normalized[:LOCAL_SEARCH_PREFIX_LENGTH]
        async with connection.execute(
            """
            SELECT id, title, original_title
            FROM media
            WHERE content_format = ? AND content_type = ?
              AND normalized_title >= ? AND normalized_title < ?
            UNION ALL
            SELECT id, title, original_title
            FROM media
            WHERE content_format = ? AND content_type = ?
              AND normalized_original_title >= ?
              AND normalized_original_title < ?
            LIMIT ?
            """,
            (
                content_format,
                content_type,
                prefix,
                _prefix_upper_bound(prefix),
                content_format,
                content_type,
                prefix,
                _prefix_upper_bound(prefix),
                LOCAL_SEARCH_CANDIDATE_LIMIT,
            ),
        ) as cursor:
            candidates = await cursor.fetchall()

        best_id = None
        best_score = 0.0
        seen_ids: set[int] = set()
        for row in candidates:
            media_id = int(row["id"])
            if media_id in seen_ids:
                continue
            seen_ids.add(media_id)
            score = title_relevance_score(dict(row), title)
            if score > best_score:
                best_id = media_id
                best_score = score

        if best_id is None or best_score < MIN_RELEVANCE:
            return None

        async with connection.execute(
            "SELECT * FROM media WHERE id = ?",
            (best_id,),
        ) as cursor:
            return await cursor.fetchone()


async def backfill_media_search_index(
    *,
    database_url: str | None = None,
) -> int:
    """Populate normalized titles for rows created before the search index."""
    updated = 0
    async with connection_scope(database_url) as connection:
        while True:
            async with connection.execute(
                """
                SELECT id, title, original_title
                FROM media
                WHERE normalized_title IS NULL
                LIMIT ?
                """,
                (SEARCH_INDEX_BACKFILL_BATCH_SIZE,),
            ) as cursor:
                rows = await cursor.fetchall()
            if not rows:
                break
            await connection.executemany(
                """
                UPDATE media
                SET normalized_title = ?, normalized_original_title = ?
                WHERE id = ?
                """,
                [
                    (
                        normalize_text(row["title"]),
                        normalize_text(row["original_title"] or ""),
                        row["id"],
                    )
                    for row in rows
                ],
            )
            updated += len(rows)
    return updated


async def _find_exact(
    connection: aiosqlite.Connection,
    normalized: str,
    content_format: str,
    content_type: str,
) -> aiosqlite.Row | None:
    async with connection.execute(
        """
        SELECT *
        FROM media
        WHERE content_format = ? AND content_type = ?
          AND normalized_title = ?
        UNION ALL
        SELECT *
        FROM media
        WHERE content_format = ? AND content_type = ?
          AND normalized_original_title = ?
        LIMIT 1
        """,
        (
            content_format,
            content_type,
            normalized,
            content_format,
            content_type,
            normalized,
        ),
    ) as cursor:
        return await cursor.fetchone()


def _prefix_upper_bound(prefix: str) -> str:
    return f"{prefix}\U0010ffff"


__all__ = (
    "LOCAL_SEARCH_CANDIDATE_LIMIT",
    "backfill_media_search_index",
    "find_media_by_title",
)
