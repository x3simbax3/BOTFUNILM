"""Last-resort handling for exceptions raised while processing updates."""

import logging

from aiogram import Router
from aiogram.types import ErrorEvent

from src.lang import UNEXPECTED_ERROR_TEXT

logger = logging.getLogger(__name__)
router = Router(name="errors")


@router.error()
async def handle_unexpected_error(event: ErrorEvent) -> bool:
    """Log an update failure, notify the user, and keep polling alive.

    The current FSM context is deliberately left untouched so the user can
    retry the failed action without losing the preceding conversation state.
    """
    exception = event.exception
    logger.error(
        "Unexpected error while processing update id=%s",
        event.update.update_id,
        exc_info=(type(exception), exception, exception.__traceback__),
    )

    try:
        callback = event.update.callback_query
        if callback is not None:
            await callback.answer(UNEXPECTED_ERROR_TEXT, show_alert=True)
        elif event.update.message is not None:
            await event.update.message.answer(UNEXPECTED_ERROR_TEXT)
    except Exception:
        # An unavailable Telegram API must not turn the error handler itself
        # into another unhandled update failure.
        logger.warning(
            "Could not notify the user about failed update id=%s",
            event.update.update_id,
            exc_info=True,
        )

    return True


__all__ = ("handle_unexpected_error", "router")
