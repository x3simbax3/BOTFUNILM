import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

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
TEST_PROCESSES = int(os.getenv("TEST_PROCESSES", "2"))
