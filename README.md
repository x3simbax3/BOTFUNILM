# BOTFUNILM

**Your personal media tracker in Telegram.**

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
git clone https://github.com/your-username/BotFunilm.git
cd BotFunilm
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

Create `config/.env`:

```env
BOT_TOKEN=your_telegram_bot_token
TMDB_API=your_tmdb_api_key_or_bearer_token
TMDB_LANG=ru-RU
DATABASE_URL=sqlite:///bot.db
DEBUG=false
```

Run the bot:

```bash
./run_bot.sh
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
