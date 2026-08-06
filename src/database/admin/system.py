"""Admin runtime feature queries."""

from __future__ import annotations

from src.database.admin.models import ALLOWED_FEATURES
from src.database.connection import connection_scope


async def is_feature_enabled(feature: str, *, database_url: str | None = None) -> bool:
    if feature not in ALLOWED_FEATURES:
        raise ValueError("Unknown feature")
    async with connection_scope(database_url) as connection:
        async with connection.execute(
            "SELECT enabled FROM bot_features WHERE feature = ?", (feature,)
        ) as cursor:
            row = await cursor.fetchone()
    return bool(row["enabled"]) if row else True
