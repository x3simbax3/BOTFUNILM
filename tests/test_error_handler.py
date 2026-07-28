import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.handlers.errors import handle_unexpected_error
from src.handlers.errors import router as errors_router
from src.lang import UNEXPECTED_ERROR_TEXT
from src.routers import router as main_router


class UnexpectedErrorHandlerTests(unittest.IsolatedAsyncioTestCase):
    def test_error_router_is_registered_globally(self) -> None:
        self.assertIn(errors_router, main_router.sub_routers)
        self.assertEqual(len(errors_router.error.handlers), 1)

    async def test_message_error_clears_fsm_state(self) -> None:
        message = SimpleNamespace(answer=AsyncMock())
        update = SimpleNamespace(update_id=42, callback_query=None, message=message)
        exception = RuntimeError("boom")
        event = SimpleNamespace(update=update, exception=exception)
        state = SimpleNamespace(clear=AsyncMock())

        with patch("src.handlers.errors.logger.error") as log_error:
            handled = await handle_unexpected_error(event, state)

        self.assertTrue(handled)
        state.clear.assert_awaited_once_with()
        message.answer.assert_awaited_once_with(UNEXPECTED_ERROR_TEXT)
        log_error.assert_called_once()

    async def test_callback_error_uses_alert(self) -> None:
        callback = SimpleNamespace(answer=AsyncMock())
        update = SimpleNamespace(update_id=43, callback_query=callback, message=None)
        event = SimpleNamespace(update=update, exception=ValueError("bad callback"))
        state = SimpleNamespace(clear=AsyncMock())

        with patch("src.handlers.errors.logger.error"):
            handled = await handle_unexpected_error(event, state)

        self.assertTrue(handled)
        callback.answer.assert_awaited_once_with(
            UNEXPECTED_ERROR_TEXT,
            show_alert=True,
        )

    async def test_notification_failure_does_not_escape_handler(self) -> None:
        message = SimpleNamespace(answer=AsyncMock(side_effect=OSError("offline")))
        update = SimpleNamespace(update_id=44, callback_query=None, message=message)
        event = SimpleNamespace(update=update, exception=RuntimeError("boom"))
        state = SimpleNamespace(clear=AsyncMock())

        with (
            patch("src.handlers.errors.logger.error"),
            patch("src.handlers.errors.logger.warning") as log_warning,
        ):
            handled = await handle_unexpected_error(event, state)

        self.assertTrue(handled)
        state.clear.assert_awaited_once_with()
        log_warning.assert_called_once()

    async def test_fsm_clear_failure_does_not_escape_handler(self) -> None:
        message = SimpleNamespace(answer=AsyncMock())
        update = SimpleNamespace(update_id=45, callback_query=None, message=message)
        event = SimpleNamespace(update=update, exception=RuntimeError("boom"))
        state = SimpleNamespace(clear=AsyncMock(side_effect=OSError("redis offline")))

        with (
            patch("src.handlers.errors.logger.error"),
            patch("src.handlers.errors.logger.warning") as log_warning,
        ):
            handled = await handle_unexpected_error(event, state)

        self.assertTrue(handled)
        message.answer.assert_awaited_once_with(UNEXPECTED_ERROR_TEXT)
        log_warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
