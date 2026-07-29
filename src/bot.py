import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import SimpleEventIsolation

from config.config import (
    BOT_TOKEN,
    DATABASE_URL,
    DEBUG,
    FSM_TTL_SECONDS,
    PROJECT_ROOT,
    REDIS_URL,
    UPDATE_TASKS_CONCURRENCY_LIMIT,
    USER_THROTTLE_MAX_UPDATES,
    USER_THROTTLE_MAX_USERS,
    USER_THROTTLE_PERIOD_SECONDS,
)
from src.database.connection import database_path
from src.database.media_search import backfill_media_search_index
from src.file_security import verify_private_files
from src.http_client import close_http_session
from src.routers import router
from src.update_throttling import UserThrottleMiddleware


def create_dispatcher() -> Dispatcher:
    """Create a dispatcher with persistent FSM storage when Redis is configured."""
    if not REDIS_URL:
        dispatcher = Dispatcher(
            events_isolation=SimpleEventIsolation(),
            disable_fsm=True,
        )
    else:
        if FSM_TTL_SECONDS <= 0:
            raise ValueError("FSM_TTL_SECONDS must be a positive integer")

        from aiogram.fsm.storage.redis import RedisStorage

        storage = RedisStorage.from_url(
            REDIS_URL,
            state_ttl=FSM_TTL_SECONDS,
            data_ttl=FSM_TTL_SECONDS,
        )
        dispatcher = Dispatcher(
            storage=storage,
            events_isolation=storage.create_isolation(),
            disable_fsm=True,
        )

    # Register the limiter between user extraction and FSM so rejected updates
    # never acquire event-isolation locks or access Redis-backed state.
    dispatcher.update.outer_middleware(
        UserThrottleMiddleware(
            max_updates=USER_THROTTLE_MAX_UPDATES,
            period_seconds=USER_THROTTLE_PERIOD_SECONDS,
            max_users=USER_THROTTLE_MAX_USERS,
        )
    )
    dispatcher.update.outer_middleware(dispatcher.fsm)
    return dispatcher


async def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG if DEBUG else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    os.umask(0o077)
    verify_private_files(
        (
            PROJECT_ROOT / "config" / ".env",
            Path(database_path(DATABASE_URL)),
        )
    )

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set in config/.env")
    if UPDATE_TASKS_CONCURRENCY_LIMIT <= 0:
        raise ValueError("UPDATE_TASKS_CONCURRENCY_LIMIT must be positive")

    indexed_rows = await backfill_media_search_index()
    if indexed_rows:
        logging.getLogger(__name__).info(
            "Indexed normalized titles for %s existing media rows",
            indexed_rows,
        )

    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.me()
        dp = create_dispatcher()
        dp.include_router(router)
        await dp.start_polling(
            bot,
            tasks_concurrency_limit=UPDATE_TASKS_CONCURRENCY_LIMIT,
        )
    finally:
        try:
            await close_http_session()
        finally:
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
