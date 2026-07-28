"""Persistence helpers for detailed user rating criteria."""

from __future__ import annotations

from collections.abc import Mapping

import aiosqlite

from src.database.connection import connection_scope

VALID_RATING_CRITERIA = frozenset(
    {"acting", "story", "visuals", "sound", "overall", "animation", "characters"}
)


def validate_rating_details(ratings: Mapping[str, int]) -> None:
    for criterion, score in ratings.items():
        if criterion not in VALID_RATING_CRITERIA:
            raise ValueError("Unknown rating criterion")
        if type(score) is not int or not 1 <= score <= 10:
            raise ValueError("Rating scores must be integers from 1 to 10")


async def replace_user_rating_details(
    connection: aiosqlite.Connection,
    user_id: int,
    media_id: int,
    ratings: Mapping[str, int],
) -> None:
    """Replace one user's detailed ratings inside the caller's transaction."""
    validate_rating_details(ratings)
    await connection.execute(
        "DELETE FROM user_media_rating_details WHERE user_id = ? AND media_id = ?",
        (user_id, media_id),
    )
    if ratings:
        await connection.executemany(
            """
            INSERT INTO user_media_rating_details (
                user_id, media_id, criterion, score, updated_at
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            [
                (user_id, media_id, criterion, score)
                for criterion, score in ratings.items()
            ],
        )


async def get_user_rating_details(
    user_id: int,
    media_id: int,
    *,
    database_url: str | None = None,
) -> dict[str, int]:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT criterion, score
            FROM user_media_rating_details
            WHERE user_id = ? AND media_id = ?
            ORDER BY criterion
            """,
            (user_id, media_id),
        ) as cursor:
            return {row["criterion"]: row["score"] for row in await cursor.fetchall()}


__all__ = (
    "get_user_rating_details",
    "replace_user_rating_details",
    "validate_rating_details",
)
