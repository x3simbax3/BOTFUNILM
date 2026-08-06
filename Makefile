PYTHON ?= uv run python
PYTEST ?= uv run pytest
TEST_PROCESSES ?= 2
ATLAS ?= atlas
COMPOSE ?= docker compose
QUALITY_PATHS := src config tests
FORMAT_PATHS := src config/config.py tests
HOST_UID ?= $(shell id -u)
HOST_GID ?= $(shell id -g)
FORMAT_VOLUMES := --volume $(CURDIR)/src:/app/src --volume $(CURDIR)/config/config.py:/app/config/config.py --volume $(CURDIR)/tests:/app/tests

.PHONY: help check compose-check test-image lint format test test-local build start up deploy start-local stop down restart logs ps secure-files migrate migration db-check db-status db-downgrade db-reset db-backup media-refresh-daily media-refresh-weekly media-refresh media-refresh-tmdb media-refresh-dry series-notify news-broadcast media-worker-logs commit
.NOTPARALLEL: check

help:
	@echo "Docker targets:"
	@echo "  make start          Build and start bot + media worker + Redis"
	@echo "  make deploy         Rebuild and recreate bot + media worker"
	@echo "  make build          Build the production runtime image"
	@echo "  make lint           Check formatting and lint in Docker"
	@echo "  make format         Fix lint issues and format source files in Docker"
	@echo "  make test           Build the test target and run tests in Docker"
	@echo "  make check          Validate Compose/DB, then run lint and tests"
	@echo "  make restart        Alias for make deploy"
	@echo "  make logs           Follow bot, media worker and Redis logs"
	@echo "  make media-worker-logs  Follow media worker logs"
	@echo "  make media-refresh-daily   Refresh due active series now"
	@echo "  make media-refresh-weekly  Refresh due series of every status now"
	@echo "  make media-refresh id=42   Refresh one catalogue series"
	@echo "  make media-refresh-tmdb id=1399  Refresh by TMDB id"
	@echo "  make media-refresh-dry id=42  Preview one refresh without writes"
	@echo "  make series-notify      Send pending series notifications now"
	@echo "  make news-broadcast     Broadcast one fresh cinema news article now"
	@echo "  make ps             Show Compose service status"
	@echo "  make stop           Stop Compose without deleting persistent data"
	@echo ""
	@echo "Local development targets:"
	@echo "  make start-local    Apply migrations and run bot through uv"
	@echo "  make secure-files   Restrict local .env and database permissions"
	@echo "  make test-local     Run tests locally through uv"
	@echo "  make db-check       Validate migration files and schema"
	@echo "  make migration name='...'  Generate a migration"
	@echo "  make db-status      Show local database migration status"
	@echo "  make db-backup      Create and verify a production backup now"

check: compose-check db-check test-image
	$(COMPOSE) --profile test run --rm test ruff format --check $(QUALITY_PATHS)
	$(COMPOSE) --profile test run --rm test ruff check $(QUALITY_PATHS)
	$(COMPOSE) --profile test run --rm test pytest -q -n $(TEST_PROCESSES)

compose-check:
	$(COMPOSE) config --quiet

test-image:
	$(COMPOSE) --profile test build test

lint: test-image
	$(COMPOSE) --profile test run --rm test ruff format --check $(QUALITY_PATHS)
	$(COMPOSE) --profile test run --rm test ruff check $(QUALITY_PATHS)

format: test-image
	$(COMPOSE) --profile test run --rm --user $(HOST_UID):$(HOST_GID) $(FORMAT_VOLUMES) test ruff check --fix $(FORMAT_PATHS)
	$(COMPOSE) --profile test run --rm --user $(HOST_UID):$(HOST_GID) $(FORMAT_VOLUMES) test ruff format $(FORMAT_PATHS)

test: test-image
	$(COMPOSE) --profile test run --rm test pytest -q -n $(TEST_PROCESSES)

test-local:
	$(PYTEST) -q -n $(TEST_PROCESSES)

build: compose-check
	$(COMPOSE) build bot media-worker

start: up

up: secure-files compose-check
	$(COMPOSE) up --detach --build

deploy: secure-files compose-check
	$(COMPOSE) up --detach --build bot media-worker

start-local: migrate
	$(PYTHON) -m src.bot

stop: down

down:
	$(COMPOSE) down

restart: deploy

logs:
	$(COMPOSE) logs --follow bot media-worker redis

media-worker-logs:
	$(COMPOSE) logs --follow media-worker

media-refresh-daily:
	$(COMPOSE) run --rm media-worker python -m src.jobs.media_worker run daily

media-refresh-weekly:
	$(COMPOSE) run --rm media-worker python -m src.jobs.media_worker run weekly

media-refresh:
	@if [ -z "$(id)" ]; then echo "Usage: make media-refresh id=42"; exit 1; fi
	$(COMPOSE) run --rm media-worker python -m src.jobs.media_worker single --id $(id)

media-refresh-tmdb:
	@if [ -z "$(id)" ]; then echo "Usage: make media-refresh-tmdb id=1399"; exit 1; fi
	$(COMPOSE) run --rm media-worker python -m src.jobs.media_worker single --tmdb-id $(id)

media-refresh-dry:
	@if [ -z "$(id)" ]; then echo "Usage: make media-refresh-dry id=42"; exit 1; fi
	$(COMPOSE) run --rm media-worker python -m src.jobs.media_worker single --id $(id) --dry-run

series-notify:
	$(COMPOSE) run --rm media-worker python -m src.jobs.media_worker notify

news-broadcast:
	$(COMPOSE) run --rm media-worker python -m src.jobs.media_worker news

ps:
	$(COMPOSE) ps

secure-files:
	chmod 600 config/.env
	install -d -m 700 backups
	@if [ -e bot.db ]; then chmod 600 bot.db; fi

migrate: secure-files
	umask 077; $(ATLAS) migrate apply --env local

migration:
	@if [ -z "$(name)" ]; then \
		echo "Usage: make migration name='describe schema change'"; \
		exit 1; \
	fi
	$(ATLAS) migrate diff "$(name)" --env local

db-check:
	$(ATLAS) migrate validate --env local
	@schema_diff="$$( $(ATLAS) schema diff --from file://migrations --to file://schema.sql --dev-url 'sqlite://dev?mode=memory&_fk=1' --format '{{ sql . }}' )"; \
		if [ -n "$$schema_diff" ]; then \
			printf '%s\n' "Schema and migrations differ:" "$$schema_diff"; \
			exit 1; \
		fi

db-status:
	$(ATLAS) migrate status --env local

db-backup:
	$(COMPOSE) run --rm backup python -m src.jobs.database_backup backup

db-downgrade:
	$(ATLAS) migrate down 1 --env local

db-reset:
	@printf '\nWARNING: This will permanently delete bot.db and all of its data.\n'; \
		printf 'Recreate the database from migrations? [y/N] '; \
		read answer; \
		case "$$answer" in \
			y|Y) ;; \
			*) echo "Database reset cancelled."; exit 1 ;; \
		esac; \
		rm -f -- bot.db bot.db-shm bot.db-wal; \
		umask 077; $(ATLAS) migrate apply --env local

commit: check
	@if [ -z "$(m)" ]; then \
		echo "Usage: make commit m='commit message'"; \
		exit 1; \
	fi
	git add -A
	@if git diff --cached --quiet; then \
		echo "No staged changes to commit."; \
		exit 1; \
	fi
	git commit -m "$(m)"
