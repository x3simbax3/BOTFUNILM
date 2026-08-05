from aiogram.fsm.state import State, StatesGroup


class MenuState(StatesGroup):
    choosing_action = State()
    choosing_library_action = State()
    choosing_settings = State()
    viewing_library = State()
    viewing_tracked = State()
    viewing_media = State()
    choosing_format = State()
    choosing_content_type = State()
    waiting_title = State()
    confirming_tmdb_guess = State()
    choosing_watch_status = State()
    choosing_tmdb_retry = State()
    rating_category = State()
    choosing_badge = State()
    tracking_series = State()


class AdminState(StatesGroup):
    waiting_broadcast_text = State()
    waiting_broadcast_photo = State()
    confirming_broadcast = State()


__all__ = ("AdminState", "MenuState")
