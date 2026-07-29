import unittest

from aiogram.types import InlineKeyboardMarkup


def callback_rows(markup: InlineKeyboardMarkup) -> list[list[str]]:
    return [[button.callback_data for button in row] for row in markup.inline_keyboard]


class KeyboardTestCase(unittest.TestCase):
    def assert_callback_rows(
        self,
        markup: InlineKeyboardMarkup,
        expected: list[list[str]],
    ) -> None:
        self.assertEqual(callback_rows(markup), expected)
