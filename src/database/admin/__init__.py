"""Public API for admin database queries."""

from src.database.admin.activity import get_admin_activity
from src.database.admin.libraries import get_admin_libraries
from src.database.admin.models import (
    ADMIN_EXPORT_USERS_LIMIT,
    ADMIN_USERS_PAGE_SIZE,
    AdminActivity,
    AdminActivityDay,
    AdminExportUser,
    AdminLibraries,
    AdminNotifications,
    AdminOverview,
    AdminPopularTitle,
    AdminSystem,
    AdminUserDetails,
    AdminUserPage,
    AdminUserSummary,
)
from src.database.admin.notifications import get_admin_notifications
from src.database.admin.system import (
    get_admin_system,
    is_feature_enabled,
    toggle_feature,
)
from src.database.admin.users import (
    get_admin_export_users,
    get_admin_overview,
    get_admin_user,
    get_admin_users,
)

__all__ = (
    "ADMIN_EXPORT_USERS_LIMIT",
    "ADMIN_USERS_PAGE_SIZE",
    "AdminActivity",
    "AdminActivityDay",
    "AdminExportUser",
    "AdminLibraries",
    "AdminNotifications",
    "AdminOverview",
    "AdminPopularTitle",
    "AdminSystem",
    "AdminUserDetails",
    "AdminUserPage",
    "AdminUserSummary",
    "get_admin_activity",
    "get_admin_export_users",
    "get_admin_libraries",
    "get_admin_notifications",
    "get_admin_overview",
    "get_admin_system",
    "get_admin_user",
    "get_admin_users",
    "is_feature_enabled",
    "toggle_feature",
)
