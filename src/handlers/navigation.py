"""Shared state transitions used across handler workflows."""

from aiogram.fsm.context import FSMContext

from src.fsm import MenuState


async def reset_to_main(state: FSMContext) -> None:
    """Discard the current workflow and make the main menu active."""
    await state.clear()
    await state.set_state(MenuState.choosing_action)


__all__ = ("reset_to_main",)
