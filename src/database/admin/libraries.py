"""Admin queries for user libraries."""

from __future__ import annotations

from src.database.admin.models import AdminLibraries, AdminPopularTitle
from src.database.connection import connection_scope


async def get_admin_libraries(*, database_url: str | None = None) -> AdminLibraries:
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            """
            SELECT COUNT(*) AS total_items,
                   COUNT(DISTINCT user_media.user_id) AS users_with_library,
                   COUNT(*) FILTER (WHERE user_media.status = 'planned') AS planned_items,
                   COUNT(*) FILTER (WHERE user_media.status = 'watching') AS watching_items,
                   COUNT(*) FILTER (WHERE user_media.status = 'completed') AS completed_items,
                   COUNT(*) FILTER (WHERE user_media.status = 'on_hold') AS on_hold_items,
                   COUNT(*) FILTER (WHERE media.content_format = 'full_length') AS full_length_items,
                   COUNT(*) FILTER (WHERE media.content_format = 'series') AS series_items,
                   COUNT(*) FILTER (WHERE media.content_type = 'movie') AS movie_items,
                   COUNT(*) FILTER (WHERE media.content_type = 'anime') AS anime_items,
                   COUNT(*) FILTER (WHERE media.content_type = 'cartoon') AS cartoon_items,
                   COUNT(*) FILTER (WHERE user_media.user_rating IS NOT NULL) AS rated_items,
                   AVG(user_media.user_rating) AS average_rating,
                   COUNT(*) FILTER (WHERE user_media.is_tracking = 1) AS tracked_series,
                   CURRENT_TIMESTAMP AS generated_at
            FROM user_media
            JOIN media ON media.id = user_media.media_id
            """
        ) as cursor:
            totals = dict(await cursor.fetchone())
        popular_by_format: dict[str, tuple[AdminPopularTitle, ...]] = {}
        for content_format in ("full_length", "series"):
            async with connection.execute(
                """
                SELECT media.id AS media_id, media.title, COUNT(*) AS library_users
                FROM user_media
                JOIN media ON media.id = user_media.media_id
                WHERE media.content_format = ?
                GROUP BY media.id
                ORDER BY library_users DESC, media.title, media.id
                LIMIT 5
                """,
                (content_format,),
            ) as cursor:
                popular_by_format[content_format] = tuple(
                    AdminPopularTitle(**dict(row)) for row in await cursor.fetchall()
                )
    return AdminLibraries(
        popular_movies=popular_by_format["full_length"],
        popular_series=popular_by_format["series"],
        **totals,
    )
