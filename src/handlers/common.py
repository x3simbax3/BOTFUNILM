"""Shared presentation helpers for Telegram handlers."""

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.lang import DESCRIPTION_NOT_FOUND, tmdb_guess_text

PHOTO_CAPTION_LIMIT = 1024
CAPTION_ELLIPSIS = "..."


async def edit_message(
    message: Message,
    text: str,
    parse_mode: str | None = None,
    reply_markup=None,
) -> None:
    if message.photo:
        await message.edit_caption(
            caption=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        return

    await message.edit_text(
        text,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
    )


async def replace_message(
    message: Message,
    text: str,
    parse_mode: str | None = None,
    reply_markup=None,
) -> None:
    if message.photo:
        await message.delete()
        await message.answer(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        return

    await edit_message(message, text, parse_mode, reply_markup)


async def is_active_tmdb_guess(
    callback: CallbackQuery,
    state: FSMContext,
) -> bool:
    if not callback.message:
        return False

    data = await state.get_data()
    return callback.message.message_id == data.get("tmdb_guess_message_id")


def tmdb_guess_caption(
    content_format: str,
    title: str,
    overview: str | None,
) -> str:
    description = overview or DESCRIPTION_NOT_FOUND
    caption_without_description = tmdb_guess_text(content_format, title, "")
    description_limit = PHOTO_CAPTION_LIMIT - len(caption_without_description)
    return tmdb_guess_text(
        content_format,
        title,
        limit_caption_description(description, description_limit),
    )


def limit_caption_description(description: str, limit: int) -> str:
    if limit <= len(CAPTION_ELLIPSIS):
        return ""
    if len(description) <= limit:
        return description

    clipped = description[: max(0, limit - len(CAPTION_ELLIPSIS))].rstrip()
    return f"{clipped}{CAPTION_ELLIPSIS}"
