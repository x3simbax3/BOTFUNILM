from aiogram import Router

from src.handlers.errors import router as errors_router
from src.handlers.library import router as library_router
from src.handlers.menu import router as menu_router
from src.handlers.rating import router as rating_router
from src.handlers.search import router as search_router
from src.handlers.series import router as series_router

router = Router(name="main")
router.include_routers(
    errors_router,
    menu_router,
    library_router,
    search_router,
    rating_router,
    series_router,
)


__all__ = ("router",)
