"""Minimal Telegram admin menu, statistics and confirmed broadcasts."""

from __future__ import annotations

import asyncio
import html
from collections.abc import Collection
from datetime import datetime
from zoneinfo import ZoneInfo

import aiosqlite
from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message, TelegramObject
from redis.exceptions import RedisError

from config.config import (
    ADMIN_USER_IDS,
    MEDIA_WORKER_TIMEZONE,
    NEWS_API_DAILY_BUDGET,
    NEWS_API_DAILY_LIMIT,
)
from src.admin_export import build_users_workbook
from src.admin_runtime import enqueue_admin_job, enqueue_custom_broadcast
from src.database.admin import (
    AdminActivity,
    AdminLibraries,
    AdminNotifications,
    AdminOverview,
    get_admin_activity,
    get_admin_export_users,
    get_admin_libraries,
    get_admin_notifications,
    get_admin_overview,
)
from src.database.news_api_usage import NewsApiUsage, get_news_api_usage
from src.fsm import AdminState
from src.handlers.common import edit_message, replace_message
from src.keyboards import (
    admin_broadcast_confirmation_keyboard,
    admin_broadcast_format_keyboard,
    admin_confirmation_keyboard,
    admin_menu_keyboard,
    admin_statistics_keyboard,
)
from src.lang import (
    ADMIN_ACCESS_DENIED,
    ADMIN_ACTION_FAILED,
    ADMIN_CALLBACK_DENIED,
    ADMIN_OVERVIEW_FAILED,
)

router = Router(name="admin")
TEXT_MESSAGE_LIMIT = 4096
PHOTO_CAPTION_LIMIT = 1024


class AdminFilter(Filter):
    def __init__(self, user_ids: Collection[int]) -> None:
        self.user_ids = frozenset(user_ids)

    async def __call__(self, event: TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        return user is not None and user.id in self.user_ids


admin_filter = AdminFilter(ADMIN_USER_IDS)


def _today() -> datetime:
    return datetime.now(ZoneInfo(MEDIA_WORKER_TIMEZONE))


def _statistics_text(
    overview: AdminOverview,
    activity: AdminActivity,
    libraries: AdminLibraries,
    notifications: AdminNotifications,
    usage: NewsApiUsage,
) -> str:
    rating = (
        "—" if libraries.average_rating is None else f"{libraries.average_rating:.1f}"
    )
    local_remaining = max(0, NEWS_API_DAILY_BUDGET - usage.requests)
    provider_limit = usage.api_limit or NEWS_API_DAILY_LIMIT
    provider_remaining = (
        "—"
        if usage.api_remaining is None
        else f"{usage.api_remaining} из {provider_limit}"
    )
    popular_movies = (
        ", ".join(html.escape(item.title) for item in libraries.popular_movies[:3])
        or "—"
    )
    popular_series = (
        ", ".join(html.escape(item.title) for item in libraries.popular_series[:3])
        or "—"
    )
    return f"""━━━  <b>Админка · Статистика</b>  ━━━
<i>Обновлено {overview.generated_at} UTC</i>

<b>👥 Пользователи</b>
Всего · <b>{overview.total_users}</b>
Активны / недоступны · {overview.active_users} / {overview.inactive_users}
Новые за 24 ч / 7 д / 30 д · {overview.new_24h} / {overview.new_7d} / {overview.new_30d}
Активны за 24 ч / 7 д / 30 д · {overview.active_24h} / {overview.active_7d} / {overview.active_30d}
С библиотекой · {overview.activated_users} ({overview.activation_percent:.1f}%)

<b>📊 Активность за 30 дней</b>
DAU / WAU / MAU · <b>{activity.dau} / {activity.wau} / {activity.mau}</b>
Новые / вернувшиеся · {activity.new_users} / {activity.returning_users}
Поиски / открытия библиотек · {activity.searches} / {activity.library_opens}
Добавления / оценки / прогресс · {activity.media_added} / {activity.ratings_set} / {activity.progress_updates}

<b>📚 Библиотеки</b>
Записей / пользователей · <b>{libraries.total_items}</b> / {libraries.users_with_library}
Хочу / смотрю / просмотрено · {libraries.planned_items} / {libraries.watching_items} / {libraries.completed_items}
Отложено · {libraries.on_hold_items}
Полный метр / сериалы · {libraries.full_length_items} / {libraries.series_items}
Кино / аниме / мультфильмы · {libraries.movie_items} / {libraries.anime_items} / {libraries.cartoon_items}
С оценкой · {libraries.rated_items}, средняя · {rating}
Отслеживаются · {libraries.tracked_series}
Популярный полный метр · {popular_movies}
Популярные сериалы · {popular_series}

<b>📨 Рассылки за 30 дней</b>
Получают новости / отказались · {notifications.news_subscribers} / {notifications.news_opted_out}
Выбрано / доставлено · {notifications.selected_30d} / {notifications.sent_30d} ({notifications.success_percent_30d:.1f}%)
Ошибки / отключены · {notifications.failed_30d} / {notifications.deactivated_30d}

<b>📰 TheNewsAPI сегодня</b>
Фактически запросов · <b>{usage.requests}</b>
Осталось локально · <b>{local_remaining} из {NEWS_API_DAILY_BUDGET}</b>
Осталось у провайдера · <b>{provider_remaining}</b> <i>(последние данные)</i>"""


async def _load_statistics():
    overview, activity, libraries, notifications = await asyncio.gather(
        get_admin_overview(),
        get_admin_activity(30),
        get_admin_libraries(),
        get_admin_notifications(),
    )
    usage = await get_news_api_usage(_today().date())
    return overview, activity, libraries, notifications, usage


@router.message(Command("admin"), F.chat.type == ChatType.PRIVATE, admin_filter)
async def show_admin_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "<b>Админка</b>\n\nВыберите действие.",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )


@router.message(Command("admin"))
async def deny_admin_menu(message: Message) -> None:
    await message.answer(ADMIN_ACCESS_DENIED)


@router.callback_query(F.data == "admin:menu", admin_filter)
async def return_to_admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message:
        await replace_message(
            callback.message,
            "<b>Админка</b>\n\nВыберите действие.",
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:stats", admin_filter)
async def show_admin_statistics(callback: CallbackQuery) -> None:
    if not callback.message:
        await callback.answer()
        return
    try:
        values = await _load_statistics()
    except (aiosqlite.Error, ValueError):
        await callback.answer(ADMIN_OVERVIEW_FAILED, show_alert=True)
        return
    await edit_message(
        callback.message,
        _statistics_text(*values),
        parse_mode="HTML",
        reply_markup=admin_statistics_keyboard(),
    )
    await callback.answer("Обновлено")


@router.callback_query(F.data == "admin:export:users", admin_filter)
async def export_admin_users(callback: CallbackQuery) -> None:
    if not callback.message:
        await callback.answer()
        return
    await callback.answer("Формирую файл")
    try:
        users = await get_admin_export_users()
        content = await asyncio.to_thread(build_users_workbook, users)
    except (aiosqlite.Error, OSError, ValueError):
        await callback.message.answer("Не удалось сформировать Excel-файл.")
        return
    filename = f"users-{_today().date().isoformat()}.xlsx"
    await callback.message.answer_document(
        BufferedInputFile(content, filename=filename),
        caption=f"Пользователей в выгрузке: {len(users)}",
    )


@router.callback_query(F.data == "admin:broadcast", admin_filter)
async def start_custom_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message:
        await edit_message(
            callback.message,
            "<b>Своя рассылка</b>\n\n"
            "Сообщение получат все активные пользователи независимо от настройки "
            "«Новости».\n\nВыберите формат сообщения.",
            parse_mode="HTML",
            reply_markup=admin_broadcast_format_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast:text", admin_filter)
async def request_broadcast_text(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminState.waiting_broadcast_text)
    if callback.message:
        await edit_message(
            callback.message,
            f"Отправьте текст рассылки — не более {TEXT_MESSAGE_LIMIT} символов.",
            reply_markup=None,
        )
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast:photo", admin_filter)
async def request_broadcast_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminState.waiting_broadcast_photo)
    if callback.message:
        await edit_message(
            callback.message,
            f"Отправьте фотографию с подписью — не более {PHOTO_CAPTION_LIMIT} символов.",
            reply_markup=None,
        )
    await callback.answer()


@router.message(AdminState.waiting_broadcast_text, admin_filter)
async def accept_broadcast_text(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if not 1 <= len(text) <= TEXT_MESSAGE_LIMIT:
        await message.answer(
            f"Текст должен содержать от 1 до {TEXT_MESSAGE_LIMIT} символов."
        )
        return
    await state.set_data({"broadcast_text": text})
    await state.set_state(AdminState.confirming_broadcast)
    await message.answer(
        text,
        parse_mode=None,
        reply_markup=admin_broadcast_confirmation_keyboard(),
    )


@router.message(AdminState.waiting_broadcast_photo, admin_filter)
async def accept_broadcast_photo(message: Message, state: FSMContext) -> None:
    caption = message.caption or ""
    if not message.photo:
        await message.answer("Нужно отправить фотографию с подписью.")
        return
    if not 1 <= len(caption) <= PHOTO_CAPTION_LIMIT:
        await message.answer(
            f"Подпись должна содержать от 1 до {PHOTO_CAPTION_LIMIT} символов."
        )
        return
    photo_file_id = message.photo[-1].file_id
    await state.set_data(
        {"broadcast_text": caption, "broadcast_photo_file_id": photo_file_id}
    )
    await state.set_state(AdminState.confirming_broadcast)
    await message.answer_photo(
        photo_file_id,
        caption=caption,
        parse_mode=None,
        reply_markup=admin_broadcast_confirmation_keyboard(),
    )


@router.callback_query(
    AdminState.confirming_broadcast,
    F.data == "admin:broadcast:send",
    admin_filter,
)
async def send_custom_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    text = data.get("broadcast_text")
    photo_file_id = data.get("broadcast_photo_file_id")
    if not isinstance(text, str) or (
        photo_file_id is not None and not isinstance(photo_file_id, str)
    ):
        await state.clear()
        await callback.answer("Черновик устарел", show_alert=True)
        return
    try:
        await enqueue_custom_broadcast(
            callback.from_user.id,
            text,
            photo_file_id=photo_file_id,
        )
    except (RedisError, ValueError):
        await callback.answer(ADMIN_ACTION_FAILED, show_alert=True)
        return
    await state.clear()
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "Рассылка поставлена в очередь.",
            reply_markup=admin_menu_keyboard(),
        )
    await callback.answer("Принято", show_alert=True)


@router.callback_query(F.data == "admin:confirm:news", admin_filter)
async def confirm_api_news(callback: CallbackQuery) -> None:
    if not callback.message:
        await callback.answer()
        return
    try:
        usage = await get_news_api_usage(_today().date())
    except aiosqlite.Error:
        await callback.answer(ADMIN_ACTION_FAILED, show_alert=True)
        return
    remaining = max(0, NEWS_API_DAILY_BUDGET - usage.requests)
    await edit_message(
        callback.message,
        "<b>Запустить новость из API?</b>\n\n"
        "Её получат только пользователи с включёнными новостями.\n"
        f"Осталось запросов в дневном бюджете: {remaining}.",
        parse_mode="HTML",
        reply_markup=admin_confirmation_keyboard("news"),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:execute:news", admin_filter)
async def execute_api_news(callback: CallbackQuery) -> None:
    if not callback.message:
        await callback.answer()
        return
    try:
        usage = await get_news_api_usage(_today().date())
        if usage.requests >= NEWS_API_DAILY_BUDGET:
            await callback.answer("Дневной бюджет запросов исчерпан", show_alert=True)
            return
        await enqueue_admin_job("news", callback.from_user.id)
    except (aiosqlite.Error, RedisError, ValueError):
        await callback.answer(ADMIN_ACTION_FAILED, show_alert=True)
        return
    await edit_message(
        callback.message,
        "<b>Админка</b>\n\nНовость поставлена в очередь.",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer("Принято", show_alert=True)


@router.callback_query(F.data.startswith("admin:"))
async def deny_admin_callback(callback: CallbackQuery) -> None:
    await callback.answer(ADMIN_CALLBACK_DENIED, show_alert=True)


__all__ = (
    "AdminFilter",
    "deny_admin_callback",
    "deny_admin_menu",
    "router",
    "show_admin_menu",
    "show_admin_statistics",
)
