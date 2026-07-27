"""Queries for library filters and library browsing."""

from __future__ import annotations

import aiosqlite

from src.database.connection import connection_scope

LIBRARY_FILTER_NAMES = frozenset(
    {
        "full_length",
        "series",
        "movie",
        "anime",
        "cartoon",
        "completed",
        "planned",
    }
)
LIBRARY_SORT_ORDERS = frozenset({"recent", "rating"})
FORMAT_FILTERS = frozenset({"full_length", "series"})
TYPE_FILTERS = frozenset({"movie", "anime", "cartoon"})
STATUS_FILTERS = frozenset({"completed", "planned"})


async def get_user_library_filters(
    user_id: int,
    *,
    database_url: str | None = None,
) -> dict[str, bool]:
    async with connection_scope(database_url) as connection:
        await connection.execute(
            "INSERT OR IGNORE INTO user_library_filters (user_id) VALUES (?)",
            (user_id,),
        )
        async with connection.execute(
            "SELECT * FROM user_library_filters WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        raise RuntimeError("Library filters were not created")
    return _filters_from_row(row)


async def update_user_library_filter(
    user_id: int,
    filter_name: str,
    *,
    database_url: str | None = None,
) -> dict[str, bool]:
    if filter_name != "all" and filter_name not in LIBRARY_FILTER_NAMES:
        raise ValueError("Unknown library filter")

    async with connection_scope(database_url) as connection:
        await connection.execute(
            "INSERT OR IGNORE INTO user_library_filters (user_id) VALUES (?)",
            (user_id,),
        )
        if filter_name == "all":
            await connection.execute(
                """
                UPDATE user_library_filters
                SET full_length = 1, series = 1,
                    movie = 1, anime = 1, cartoon = 1,
                    completed = 1, planned = 1
                WHERE user_id = ?
                """,
                (user_id,),
            )
        elif filter_name in FORMAT_FILTERS:
            await connection.execute(
                f"""
                UPDATE user_library_filters
                SET full_length = ?, series = ?
                WHERE user_id = ?
                """,
                (
                    filter_name == "full_length",
                    filter_name == "series",
                    user_id,
                ),
            )
        elif filter_name in TYPE_FILTERS:
            await connection.execute(
                """
                UPDATE user_library_filters
                SET movie = ?, anime = ?, cartoon = ?
                WHERE user_id = ?
                """,
                (
                    filter_name == "movie",
                    filter_name == "anime",
                    filter_name == "cartoon",
                    user_id,
                ),
            )
        else:
            await connection.execute(
                """
                UPDATE user_library_filters
                SET completed = ?, planned = ?
                WHERE user_id = ?
                """,
                (
                    filter_name == "completed",
                    filter_name == "planned",
                    user_id,
                ),
            )
        async with connection.execute(
            "SELECT * FROM user_library_filters WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        raise RuntimeError("Library filters were not updated")
    return _filters_from_row(row)


async def list_user_library(
    user_id: int,
    filters: dict[str, bool],
    *,
    limit: int = 20,
    offset: int = 0,
    sort_order: str = "recent",
    database_url: str | None = None,
) -> list[aiosqlite.Row]:
    if limit <= 0 or offset < 0:
        raise ValueError("Invalid library page")
    if sort_order not in LIBRARY_SORT_ORDERS:
        raise ValueError("Unknown library sort order")

    order_by = (
        "um.user_rating IS NULL, um.user_rating DESC, "
        "m.rating IS NULL, m.rating DESC, um.added_at DESC, m.id DESC"
        if sort_order == "rating"
        else "um.added_at DESC, m.id DESC"
    )
    status_unfiltered = filters.get("completed", False) and filters.get(
        "planned", False
    )

    async with connection_scope(database_url) as connection:
        async with connection.execute(
            f"""
            SELECT m.*, um.status AS user_status, um.user_rating,
                   um.episodes_watched, um.last_watched_at
            FROM user_media AS um
            JOIN media AS m ON m.id = um.media_id
            WHERE um.user_id = ?
              AND ((? AND m.content_format = 'full_length')
                   OR (? AND m.content_format = 'series'))
              AND ((? AND m.content_type = 'movie')
                   OR (? AND m.content_type = 'anime')
                   OR (? AND m.content_type = 'cartoon'))
              AND (? OR (? AND (um.status = 'completed'
                                OR COALESCE(um.episodes_watched, 0) > 0))
                     OR (? AND um.status = 'planned'))
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
            """,
            (
                user_id,
                filters.get("full_length", False),
                filters.get("series", False),
                filters.get("movie", False),
                filters.get("anime", False),
                filters.get("cartoon", False),
                status_unfiltered,
                filters.get("completed", False),
                filters.get("planned", False),
                limit,
                offset,
            ),
        ) as cursor:
            return await cursor.fetchall()


async def get_user_library_item(
    user_id: int,
    media_id: int,
    *,
    database_url: str | None = None,
) -> aiosqlite.Row | None:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT m.*, um.status AS user_status, um.user_rating,
                   um.episodes_watched, um.last_watched_at
            FROM user_media AS um
            JOIN media AS m ON m.id = um.media_id
            WHERE um.user_id = ? AND um.media_id = ?
            """,
            (user_id, media_id),
        ) as cursor:
            return await cursor.fetchone()


def _filters_from_row(row: aiosqlite.Row) -> dict[str, bool]:
    return {name: bool(row[name]) for name in LIBRARY_FILTER_NAMES}


__all__ = (
    "LIBRARY_FILTER_NAMES",
    "LIBRARY_SORT_ORDERS",
    "get_user_library_filters",
    "get_user_library_item",
    "list_user_library",
    "update_user_library_filter",
)
