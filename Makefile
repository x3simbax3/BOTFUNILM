PYTHON ?= uv run python
PYTEST ?= uv run pytest
TEST_PROCESSES ?= 1
ATLAS ?= atlas
COMPOSE ?= docker compose
QUALITY_PATHS := src config tests
FORMAT_PATHS := src config/config.py tests
HOST_UID ?= $(shell id -u)
HOST_GID ?= $(shell id -g)
FORMAT_VOLUMES := --volume $(CURDIR)/src:/app/src --volume $(CURDIR)/config/config.py:/app/config/config.py --volume $(CURDIR)/tests:/app/tests

.PHONY: help check compose-check test-image lint format test test-local build start up start-local stop down restart logs ps migrate migration db-check db-status db-downgrade db-reset commit
.NOTPARALLEL: check

help:
	@echo "Docker targets:"
	@echo "  make start          Build and start bot + Redis through Compose"
	@echo "  make build          Build the production bot image"
	@echo "  make lint           Check formatting and lint in Docker"
	@echo "  make format         Fix lint issues and format source files in Docker"
	@echo "  make test           Build the test target and run tests in Docker"
	@echo "  make check          Validate Compose/DB, then run lint and tests"
	@echo "  make restart        Restart only the bot container"
	@echo "  make logs           Follow bot and Redis logs"
	@echo "  make ps             Show Compose service status"
	@echo "  make stop           Stop Compose without deleting persistent data"
	@echo ""
	@echo "Local development targets:"
	@echo "  make start-local    Apply migrations and run bot through uv"
	@echo "  make test-local     Run tests locally through uv"
	@echo "  make db-check       Validate migration files and schema"
	@echo "  make migration name='...'  Generate a migration"
	@echo "  make db-status      Show local database migration status"

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
	$(COMPOSE) build bot

start: up

up: compose-check
	$(COMPOSE) up --detach --build

start-local: migrate
	$(PYTHON) -m src.bot

stop: down

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart bot

logs:
	$(COMPOSE) logs --follow bot redis

ps:
	$(COMPOSE) ps

migrate:
	$(ATLAS) migrate apply --env local

migration:
	@if [ -z "$(name)" ]; then \
		echo "Usage: make migration name='describe schema change'"; \
		exit 1; \
	fi
	$(ATLAS) migrate diff "$(name)" --env local

db-check:
	$(ATLAS) migrate validate --env local
	$(ATLAS) schema diff --from file://migrations --to file://schema.sql --dev-url 'sqlite://dev?mode=memory&_fk=1'

db-status:
	$(ATLAS) migrate status --env local

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
		$(ATLAS) migrate apply --env local

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
