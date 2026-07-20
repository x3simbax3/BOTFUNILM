from aiogram import Router

from src.handlers import start_router


router = Router(name="main")
router.include_router(start_router)


__all__ = ("router",)
