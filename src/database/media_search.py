"""Bounded fuzzy lookup in the local media catalogue."""

import aiosqlite

from src.database.connection import connection_scope
from src.tmdb_matching import MIN_RELEVANCE, normalize_text, title_relevance_score

LOCAL_SEARCH_CANDIDATE_LIMIT = 100
LOCAL_SEARCH_PREFIX_LENGTH = 8
LOCAL_SEARCH_TERM_LENGTH = 3
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

        candidates = await _find_candidates(
            connection,
            normalized,
            content_format,
            content_type,
        )

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
                   OR (normalized_title != '' AND NOT EXISTS (
                        SELECT 1 FROM media_search_terms
                        WHERE media_id = media.id
                   ))
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
            for row in rows:
                await replace_media_search_terms(
                    connection,
                    int(row["id"]),
                    str(row["title"]),
                    row["original_title"],
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


async def _find_candidates(
    connection: aiosqlite.Connection,
    normalized: str,
    content_format: str,
    content_type: str,
) -> list[aiosqlite.Row]:
    terms = sorted(media_search_terms(normalized))
    if len(normalized) < LOCAL_SEARCH_TERM_LENGTH:
        prefix = normalized[:LOCAL_SEARCH_PREFIX_LENGTH]
        async with connection.execute(
            """
            SELECT id, title, original_title
            FROM media
            WHERE content_format = ? AND content_type = ?
              AND normalized_title >= ? AND normalized_title < ?
            LIMIT ?
            """,
            (
                content_format,
                content_type,
                prefix,
                _prefix_upper_bound(prefix),
                LOCAL_SEARCH_CANDIDATE_LIMIT,
            ),
        ) as cursor:
            return await cursor.fetchall()

    placeholders = ", ".join("?" for _ in terms)
    async with connection.execute(
        f"""
        SELECT media.id, media.title, media.original_title
        FROM media_search_terms
        JOIN media ON media.id = media_search_terms.media_id
        WHERE media_search_terms.term IN ({placeholders})
          AND media.content_format = ? AND media.content_type = ?
        GROUP BY media.id
        ORDER BY COUNT(*) DESC, media.id
        LIMIT ?
        """,
        (*terms, content_format, content_type, LOCAL_SEARCH_CANDIDATE_LIMIT),
    ) as cursor:
        return await cursor.fetchall()


def media_search_terms(value: str) -> set[str]:
    normalized = normalize_text(value)
    if not normalized:
        return set()
    if len(normalized) <= LOCAL_SEARCH_TERM_LENGTH:
        return {normalized}
    return {
        normalized[index : index + LOCAL_SEARCH_TERM_LENGTH]
        for index in range(len(normalized) - LOCAL_SEARCH_TERM_LENGTH + 1)
    }


async def replace_media_search_terms(
    connection: aiosqlite.Connection,
    media_id: int,
    title: str,
    original_title: str | None,
) -> None:
    await connection.execute(
        "DELETE FROM media_search_terms WHERE media_id = ?",
        (media_id,),
    )
    terms = sorted(media_search_terms(title) | media_search_terms(original_title or ""))
    if terms:
        await connection.executemany(
            "INSERT INTO media_search_terms (media_id, term) VALUES (?, ?)",
            [(media_id, term) for term in terms],
        )


__all__ = (
    "LOCAL_SEARCH_CANDIDATE_LIMIT",
    "backfill_media_search_index",
    "find_media_by_title",
    "media_search_terms",
    "replace_media_search_terms",
)
