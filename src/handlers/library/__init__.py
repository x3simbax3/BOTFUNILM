"""Public library-handler facade and router registration."""

from aiogram import Router

from .actions import router as actions_router
from .item import library_item_caption, media_id_from_start, show_library_item
from .listing import router as listing_router

router = Router(name="library")
router.include_routers(listing_router, actions_router)

__all__ = (
    "library_item_caption",
    "media_id_from_start",
    "router",
    "show_library_item",
)
