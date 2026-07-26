import os
from pathlib import Path

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
TMDB_API = os.getenv("TMDB_API", "")
TMDB_URL = os.getenv("TMDB_URL", "https://api.themoviedb.org/3")
TMDB_LANG = os.getenv("TMDB_LANG", "ru-RU")
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", PROJECT_ROOT / "media")).resolve()
REDIS_URL = os.getenv("REDIS_URL", "")
FSM_TTL_SECONDS = int(os.getenv("FSM_TTL_SECONDS", "86400"))
TEST_PROCESSES = int(os.getenv("TEST_PROCESSES", "2"))
