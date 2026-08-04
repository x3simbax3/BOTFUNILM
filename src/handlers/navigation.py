"""Shared state transitions used across handler workflows."""

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

from src.database.bot_users import get_news_enabled
from src.fsm import MenuState
from src.keyboards import main_menu_keyboard


async def reset_to_main(state: FSMContext) -> None:
    """Discard the current workflow and make the main menu active."""
    await state.clear()
    await state.set_state(MenuState.choosing_action)


async def user_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return main_menu_keyboard(await get_news_enabled(user_id))


__all__ = ("reset_to_main", "user_main_menu_keyboard")
