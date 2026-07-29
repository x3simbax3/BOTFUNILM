"""Asynchronous SQLite connection and transaction helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite

from config.config import DATABASE_URL


def database_path(database_url: str | None = None) -> str:
    url = database_url or DATABASE_URL
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise ValueError("Only sqlite:/// database URLs are supported")

    path = url[len(prefix) :]
    if not path:
        raise ValueError("SQLite database path cannot be empty")
    return path


async def connect_database(database_url: str | None = None) -> aiosqlite.Connection:
    """Open an asynchronous SQLite connection for direct cursor use."""
    connection = await aiosqlite.connect(database_path(database_url), timeout=5)
    connection.row_factory = aiosqlite.Row
    await connection.execute("PRAGMA foreign_keys = ON")
    await connection.execute("PRAGMA busy_timeout = 5000")
    return connection


@asynccontextmanager
async def connection_scope(
    database_url: str | None = None,
) -> AsyncIterator[aiosqlite.Connection]:
    """Commit on success, roll back on error, and always close the connection."""
    connection = await connect_database(database_url)
    try:
        yield connection
    except BaseException:
        await connection.rollback()
        raise
    else:
        await connection.commit()
    finally:
        await connection.close()


@asynccontextmanager
async def existing_or_connection_scope(
    connection: aiosqlite.Connection | None = None,
    *,
    database_url: str | None = None,
) -> AsyncIterator[aiosqlite.Connection]:
    """Reuse a caller-owned transaction or open and own a new one."""
    if connection is not None:
        if database_url is not None:
            raise ValueError("database_url cannot be used with an existing connection")
        yield connection
        return

    async with connection_scope(database_url) as owned_connection:
        yield owned_connection


__all__ = (
    "connect_database",
    "connection_scope",
    "database_path",
    "existing_or_connection_scope",
)
