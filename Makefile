PYTHON ?= venv/bin/python
PYTEST ?= $(PYTHON) -m pytest

.PHONY: help check test start commit

help:
	@echo "Targets:"
	@echo "  make check          Run project checks"
	@echo "  make test           Run tests when test files exist"
	@echo "  make start          Run checks, then start the bot"
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

start: check
	$(PYTHON) -m src.bot

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
