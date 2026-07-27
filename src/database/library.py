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
            """
            INSERT OR IGNORE INTO user_library_filters
                (user_id, completed, planned)
            VALUES (?, 1, 0)
            """,
            (user_id,),
        )
        # Normalize rows created with the old all-statuses default.
        await connection.execute(
            """
            UPDATE user_library_filters
            SET planned = 0
            WHERE user_id = ? AND completed = 1 AND planned = 1
            """,
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
            """
            INSERT OR IGNORE INTO user_library_filters
                (user_id, completed, planned)
            VALUES (?, 1, 0)
            """,
            (user_id,),
        )
        if filter_name == "all":
            await connection.execute(
                """
                UPDATE user_library_filters
                SET full_length = 1, series = 1,
                    movie = 1, anime = 1, cartoon = 1,
                    completed = 1, planned = 0
                WHERE user_id = ?
                """,
                (user_id,),
            )
        else:
            if filter_name in FORMAT_FILTERS:
                group = ("full_length", "series")
            elif filter_name in TYPE_FILTERS:
                group = ("movie", "anime", "cartoon")
            else:
                group = ("completed", "planned")

            async with connection.execute(
                "SELECT * FROM user_library_filters WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                current = await cursor.fetchone()
            if current is None:
                raise RuntimeError("Library filters were not created")

            # Formats and types can return to an unfiltered group. A watch
            # status is mandatory, so clicking it keeps it selected.
            restore_group = (
                filter_name not in STATUS_FILTERS
                and bool(current[filter_name])
                and sum(bool(current[name]) for name in group) == 1
            )
            values = [True if restore_group else name == filter_name for name in group]
            assignments = ", ".join(f"{name} = ?" for name in group)
            await connection.execute(
                f"UPDATE user_library_filters SET {assignments} WHERE user_id = ?",
                (*values, user_id),
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
