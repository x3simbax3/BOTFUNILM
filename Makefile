PYTHON ?= venv/bin/python
PYTEST ?= $(PYTHON) -m pytest
ATLAS ?= atlas

.PHONY: help check test start migrate migration db-check db-status db-downgrade commit

help:
	@echo "Targets:"
	@echo "  make check          Run project checks"
	@echo "  make test           Run tests when test files exist"
	@echo "  make migrate        Apply all pending database migrations"
	@echo "  make migration name='...'  Generate a migration from schema.sql changes"
	@echo "  make db-check       Validate migration files and checksums"
	@echo "  make db-status      Show applied and pending migrations"
	@echo "  make db-downgrade   Revert the latest migration"
	@echo "  make start          Run checks, migrations, then start the bot"
	@echo "  make commit m='...' Run checks, stage changes, and commit"

check:
	$(PYTHON) -m compileall -q src config tests
	$(MAKE) test

test:
	@if find tests -type f \( -name 'test_*.py' -o -name '*_test.py' \) | grep -q .; then \
		$(PYTEST); \
	else \
		echo "No tests found yet. Skipping pytest."; \
	fi

start: check migrate
	$(PYTHON) -m src.bot

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
