import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

PROJECT_ROOT = Path(__file__).resolve().parents[1]

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot.db")
DEBUG = os.getenv("DEBUG", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def parse_admin_user_ids(value: str) -> frozenset[int]:
    """Parse a comma-separated list of positive Telegram user IDs."""
    user_ids: set[int] = set()
    for raw_user_id in value.split(","):
        user_id_text = raw_user_id.strip()
        if not user_id_text:
            continue
        if not user_id_text.isascii() or not user_id_text.isdigit():
            raise ValueError("ADMIN_USER_IDS must contain integers separated by commas")
        user_id = int(user_id_text)
        if user_id <= 0:
            raise ValueError("ADMIN_USER_IDS must contain positive integers")
        user_ids.add(user_id)
    return frozenset(user_ids)


ADMIN_USER_IDS = parse_admin_user_ids(os.getenv("ADMIN_USER_IDS", ""))
TMDB_API = os.getenv("TMDB_API", "")
TMDB_ALLOWED_HOSTS = frozenset(
    host.strip().lower().rstrip(".")
    for host in os.getenv("TMDB_ALLOWED_HOSTS", "api.themoviedb.org").split(",")
    if host.strip()
)


def validate_tmdb_url(url: str, allowed_hosts: frozenset[str]) -> str:
    """Return a safe TMDB base URL or fail before a bearer token can be sent."""
    try:
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("TMDB_URL must be a valid HTTPS URL") from exc

    if parsed.scheme.lower() != "https" or not hostname:
        raise ValueError("TMDB_URL must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("TMDB_URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("TMDB_URL must not contain a query or fragment")
    if hostname not in allowed_hosts:
        raise ValueError(
            f"TMDB_URL host {hostname!r} is not listed in TMDB_ALLOWED_HOSTS"
        )
    return url.rstrip("/")


TMDB_URL = validate_tmdb_url(
    os.getenv("TMDB_URL", "https://api.themoviedb.org/3"),
    TMDB_ALLOWED_HOSTS,
)
TMDB_LANG = os.getenv("TMDB_LANG", "ru-RU")
TMDB_REGION = os.getenv("TMDB_REGION", "RU").strip().upper()
if len(TMDB_REGION) != 2 or not TMDB_REGION.isalpha():
    raise ValueError("TMDB_REGION must be a two-letter country code")
TMDB_MAX_CONCURRENCY = int(os.getenv("TMDB_MAX_CONCURRENCY", "3"))
TMDB_MAX_REQUESTS_PER_SECOND = int(os.getenv("TMDB_MAX_REQUESTS_PER_SECOND", "9"))
TMDB_QUEUE_TIMEOUT_SECONDS = float(os.getenv("TMDB_QUEUE_TIMEOUT_SECONDS", "5"))
TMDB_RATE_LIMIT_COOLDOWN_SECONDS = float(
    os.getenv("TMDB_RATE_LIMIT_COOLDOWN_SECONDS", "2")
)
TMDB_MAX_RESPONSE_BYTES = int(os.getenv("TMDB_MAX_RESPONSE_BYTES", str(5 * 1024**2)))
POSTER_ALLOWED_HOSTS = frozenset(
    host.strip().lower().rstrip(".")
    for host in os.getenv("POSTER_ALLOWED_HOSTS", "image.tmdb.org").split(",")
    if host.strip()
)
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", PROJECT_ROOT / "media")).resolve()
SQLITE_BUSY_TIMEOUT_MS = int(os.getenv("SQLITE_BUSY_TIMEOUT_MS", "15000"))
REDIS_URL = os.getenv("REDIS_URL", "")
FSM_TTL_SECONDS = int(os.getenv("FSM_TTL_SECONDS", "86400"))
UPDATE_TASKS_CONCURRENCY_LIMIT = int(os.getenv("UPDATE_TASKS_CONCURRENCY_LIMIT", "32"))
USER_THROTTLE_MAX_UPDATES = int(os.getenv("USER_THROTTLE_MAX_UPDATES", "5"))
USER_THROTTLE_PERIOD_SECONDS = float(os.getenv("USER_THROTTLE_PERIOD_SECONDS", "1"))
USER_THROTTLE_MAX_USERS = int(os.getenv("USER_THROTTLE_MAX_USERS", "10000"))
TEST_PROCESSES = int(os.getenv("TEST_PROCESSES", "2"))
THENEWSAPI_KEY = os.getenv("THENEWSAPI_KEY", "")
MEDIA_WORKER_TIMEZONE = os.getenv("MEDIA_WORKER_TIMEZONE", "Europe/Moscow")
MEDIA_REFRESH_BATCH_SIZE = int(os.getenv("MEDIA_REFRESH_BATCH_SIZE", "50"))
MEDIA_REFRESH_CONCURRENCY = int(os.getenv("MEDIA_REFRESH_CONCURRENCY", "3"))
MEDIA_REFRESH_LOCK_TTL_SECONDS = int(
    os.getenv("MEDIA_REFRESH_LOCK_TTL_SECONDS", str(6 * 60 * 60))
)
MEDIA_REFRESH_RETRIES = int(os.getenv("MEDIA_REFRESH_RETRIES", "3"))
