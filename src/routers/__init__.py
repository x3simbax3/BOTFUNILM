from aiogram import Router

from src.handlers import start_router
from src.handlers.errors import router as errors_router


router = Router(name="main")
router.include_routers(errors_router, start_router)


__all__ = ("router",)
