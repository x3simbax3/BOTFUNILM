"""Last-resort handling for exceptions raised while processing updates."""

import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import ErrorEvent

from src.lang import UNEXPECTED_ERROR_TEXT
from src.logging_config import safe_exception_info

logger = logging.getLogger(__name__)
router = Router(name="errors")


@router.error()
async def handle_unexpected_error(event: ErrorEvent, state: FSMContext) -> bool:
    """Log an update failure, reset its FSM context, and keep polling alive."""
    exception = event.exception
    logger.error(
        "Unexpected error while processing update id=%s",
        event.update.update_id,
        exc_info=safe_exception_info(exception),
    )

    try:
        await state.clear()
    except Exception as clear_error:
        # A storage outage must not turn the error handler itself into another
        # unhandled update failure.
        logger.warning(
            "Could not clear FSM state after failed update id=%s",
            event.update.update_id,
            exc_info=safe_exception_info(clear_error),
        )

    try:
        callback = event.update.callback_query
        if callback is not None:
            await callback.answer(UNEXPECTED_ERROR_TEXT, show_alert=True)
        elif event.update.message is not None:
            await event.update.message.answer(UNEXPECTED_ERROR_TEXT)
    except Exception as notification_error:
        # An unavailable Telegram API must not turn the error handler itself
        # into another unhandled update failure.
        logger.warning(
            "Could not notify the user about failed update id=%s",
            event.update.update_id,
            exc_info=safe_exception_info(notification_error),
        )

    return True


__all__ = ("handle_unexpected_error", "router")
