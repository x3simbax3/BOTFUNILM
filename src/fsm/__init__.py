from aiogram.fsm.state import State, StatesGroup


class MenuState(StatesGroup):
    choosing_action = State()
    choosing_format = State()
    choosing_content_type = State()
    waiting_title = State()


__all__ = ("MenuState",)
