import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import SimpleEventIsolation

from config.config import BOT_TOKEN, DEBUG, FSM_TTL_SECONDS, REDIS_URL
from src.http_client import close_http_session
from src.routers import router


def create_dispatcher() -> Dispatcher:
    """Create a dispatcher with persistent FSM storage when Redis is configured."""
    if not REDIS_URL:
        return Dispatcher(events_isolation=SimpleEventIsolation())
    if FSM_TTL_SECONDS <= 0:
        raise ValueError("FSM_TTL_SECONDS must be a positive integer")

    from aiogram.fsm.storage.redis import RedisStorage

    storage = RedisStorage.from_url(
        REDIS_URL,
        state_ttl=FSM_TTL_SECONDS,
        data_ttl=FSM_TTL_SECONDS,
    )
    return Dispatcher(
        storage=storage,
        events_isolation=storage.create_isolation(),
    )


async def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG if DEBUG else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set in config/.env")

    bot = Bot(token=BOT_TOKEN)
    await bot.me()
    dp = create_dispatcher()
    dp.include_router(router)

    try:
        await dp.start_polling(bot)
    finally:
        await close_http_session()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
