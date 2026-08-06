"""Models and constants for admin database queries."""

from __future__ import annotations

from dataclasses import dataclass

ADMIN_EXPORT_USERS_LIMIT = 10_000
ALLOWED_FEATURES = frozenset({"media_refresh", "notifications", "news"})


@dataclass(frozen=True)
class AdminOverview:
    total_users: int
    active_users: int
    inactive_users: int
    new_24h: int
    new_7d: int
    new_30d: int
    active_24h: int
    active_7d: int
    active_30d: int
    activated_users: int
    library_items: int
    rated_items: int
    tracked_series: int
    news_users: int
    generated_at: str

    @property
    def activation_percent(self) -> float:
        if not self.total_users:
            return 0.0
        return self.activated_users * 100 / self.total_users

    @property
    def average_library_items(self) -> float:
        if not self.total_users:
            return 0.0
        return self.library_items / self.total_users


@dataclass(frozen=True)
class AdminExportUser:
    user_id: int
    username: str | None
    display_name: str | None
    is_active: int
    news_enabled: int
    started_at: str
    last_started_at: str
    last_activity_at: str
    library_items: int
    planned_items: int
    watching_items: int
    completed_items: int
    on_hold_items: int
    rated_items: int
    tracked_series: int


@dataclass(frozen=True)
class AdminActivityDay:
    event_date: str
    active_users: int
    new_users: int
    returning_users: int


@dataclass(frozen=True)
class AdminActivity:
    days: int
    dau: int
    wau: int
    mau: int
    new_users: int
    returning_users: int
    searches: int
    library_opens: int
    media_added: int
    ratings_set: int
    progress_updates: int
    daily: tuple[AdminActivityDay, ...]
    generated_at: str


@dataclass(frozen=True)
class AdminPopularTitle:
    media_id: int
    title: str
    library_users: int


@dataclass(frozen=True)
class AdminLibraries:
    total_items: int
    users_with_library: int
    planned_items: int
    watching_items: int
    completed_items: int
    on_hold_items: int
    full_length_items: int
    series_items: int
    movie_items: int
    anime_items: int
    cartoon_items: int
    rated_items: int
    average_rating: float | None
    tracked_series: int
    popular_movies: tuple[AdminPopularTitle, ...]
    popular_series: tuple[AdminPopularTitle, ...]
    generated_at: str

    @property
    def average_items_per_user(self) -> float:
        if not self.users_with_library:
            return 0.0
        return self.total_items / self.users_with_library


@dataclass(frozen=True)
class AdminNotifications:
    news_subscribers: int
    news_opted_out: int
    series_subscribers: int
    series_subscriptions: int
    pending_series_notifications: int
    sent_series_notifications: int
    pending_release_notifications: int
    sent_release_notifications: int
    news_sent_30d: int
    release_messages_sent_30d: int
    selected_30d: int
    sent_30d: int
    failed_30d: int
    deactivated_30d: int
    blocked_users: int
    last_delivery_at: str | None
    generated_at: str

    @property
    def success_percent_30d(self) -> float:
        if not self.selected_30d:
            return 0.0
        return self.sent_30d * 100 / self.selected_30d
