<div align="center">
  <img src="https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif" width="160" alt="Typing cat">

  <h1>BOTFUNILM</h1>

  <p><strong>Your personal media tracker in Telegram.</strong></p>

  <p>
    <a href="https://github.com/x3simbax3/BOTFUNILM/commits/main">
      <img src="https://img.shields.io/github/last-commit/x3simbax3/BOTFUNILM?style=for-the-badge&logo=github&color=111827" alt="Last commit">
    </a>
    <a href="https://github.com/x3simbax3/BOTFUNILM/issues">
      <img src="https://img.shields.io/github/issues/x3simbax3/BOTFUNILM?style=for-the-badge&logo=github&color=2563eb" alt="Issues">
    </a>
    <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+">
    <img src="https://img.shields.io/badge/aiogram-3.30.0-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="aiogram 3.30.0">
    <img src="https://img.shields.io/badge/TMDB-powered-01B4E4?style=for-the-badge&logo=themoviedatabase&logoColor=white" alt="TMDB powered">
    <img src="https://img.shields.io/badge/self--hostable-yes-10b981?style=for-the-badge" alt="Self-hostable">
  </p>

  <p>
    <a href="https://github.com/topics/telegram-bot"><img src="https://img.shields.io/badge/topic-telegram--bot-2CA5E0?style=flat-square" alt="telegram-bot"></a>
    <a href="https://github.com/topics/media-tracker"><img src="https://img.shields.io/badge/topic-media--tracker-f97316?style=flat-square" alt="media-tracker"></a>
    <a href="https://github.com/topics/movie-tracker"><img src="https://img.shields.io/badge/topic-movie--tracker-ef4444?style=flat-square" alt="movie-tracker"></a>
    <a href="https://github.com/topics/anime"><img src="https://img.shields.io/badge/topic-anime-a855f7?style=flat-square" alt="anime"></a>
    <a href="https://github.com/topics/tv-series"><img src="https://img.shields.io/badge/topic-tv--series-14b8a6?style=flat-square" alt="tv-series"></a>
    <a href="https://github.com/topics/tmdb"><img src="https://img.shields.io/badge/topic-tmdb-01B4E4?style=flat-square" alt="tmdb"></a>
    <a href="https://github.com/topics/python"><img src="https://img.shields.io/badge/topic-python-3776AB?style=flat-square" alt="python"></a>
    <a href="https://github.com/topics/self-hosted"><img src="https://img.shields.io/badge/topic-self--hosted-10b981?style=flat-square" alt="self-hosted"></a>
  </p>
</div>

## Topics

`telegram-bot` `media-tracker` `movie-tracker` `anime` `tv-series` `tmdb` `python` `aiogram` `self-hosted` `watchlist`

BOTFUNILM is a sleek, open-source Telegram bot for beautifully logging and organizing everything you watch: movies, anime, and TV series. Track seasons, keep your watch history in one place, follow clean statistics, and never lose the next episode again.

> Early development. Stars, issues, ideas, and contributions are highly appreciated.

## What It Does

- Log movies, anime, and TV shows with watch status
- Track series season by season, so you always know where you left off
- Build clean watching statistics and personal insights
- Get smart notifications when new episodes drop
- Parse titles through TMDB, with future multi-source support
- Keep the core modular, hackable, and self-hostable
- Stay fast, minimal, and fully Telegram-native

## Tech Stack

- **Python**
- **aiogram 3**
- **TMDB API**
- **SQLite / PostgreSQL-ready configuration**
- **Open-source, self-hostable core**

## Project Status

BOTFUNILM is currently in active early development. The foundation is being built around a simple Telegram-native experience, TMDB-powered media lookup, and a storage layer that can grow from local SQLite to PostgreSQL.

Planned areas:

- Watchlists and status flows
- Season and episode progress
- Statistics dashboard inside Telegram
- Release tracking and notifications
- More metadata providers beyond TMDB

## Quick Start

Clone the repository:

```bash
git clone https://github.com/x3simbax3/BOTFUNILM.git
cd BOTFUNILM
```

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Install the Atlas migration CLI:

```bash
curl -sSf https://atlasgo.sh | sh
```

Create `config/.env`:

```env
BOT_TOKEN=your_telegram_bot_token
TMDB_API=your_tmdb_bearer_token
TMDB_LANG=ru-RU
DATABASE_URL=sqlite:///bot.db
DEBUG=false
```

Run the bot:

```bash
./run_bot.sh
```

## Database and migrations

The application uses SQLite through asynchronous `aiosqlite` calls. Queries are
plain SQL functions in `src/database/queries.py`; there is no ORM. Atlas manages
versioned SQL migrations, while `schema.sql` describes the desired schema.

The Python database URL remains configured in `config/.env`:

```env
DATABASE_URL=sqlite:///bot.db
```

Apply all migrations:

```bash
make migrate
```

Starting through `make start` or `./run_bot.sh` applies pending migrations before
the bot starts. The local Atlas environment targets `bot.db` in `atlas.hcl`.

After changing `schema.sql`, generate and inspect a SQL migration, then apply it:

```bash
make migration name="add media runtime"
make migrate
```

Useful migration commands:

```bash
make db-status
make db-check      # validates migration order and checksums
make db-downgrade  # reverts one migration; review data-loss risk first
```

## TMDB Search Helper

For quick manual TMDB checks, use:

```bash
./tmdb_search.sh
```

The script reads `TMDB_API` from your environment or from `config/.env`.

## Contributing

Ideas, bug reports, feature proposals, and pull requests are welcome. BOTFUNILM is intentionally small and modular, so it should be easy to inspect, extend, and self-host.

Good first contribution areas:

- Telegram UX flows
- Media status models
- TMDB parsing improvements
- Storage layer implementation
- Tests and development tooling

## License

License is not specified yet.
