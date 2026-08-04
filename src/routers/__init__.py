from aiogram import Router

from src.handlers.admin import router as admin_router
from src.handlers.errors import router as errors_router
from src.handlers.library import router as library_router
from src.handlers.menu import router as menu_router
from src.handlers.rating import router as rating_router
from src.handlers.search import router as search_router
from src.handlers.series import router as series_router
from src.handlers.tracking import router as tracking_router

router = Router(name="main")
router.include_routers(
    errors_router,
    admin_router,
    menu_router,
    library_router,
    search_router,
    rating_router,
    series_router,
    tracking_router,
)


__all__ = ("router",)
