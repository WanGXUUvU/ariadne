.PHONY: format format-check lint lint-fix test-unit test-integration test-all

BLACK := ./.venv/bin/black
RUFF := ./.venv/bin/ruff

format:
	$(BLACK) backend

format-check:
	$(BLACK) --check backend

lint:
	$(RUFF) check backend

lint-fix:
	$(RUFF) check --fix backend

test-unit:
	python3 -m unittest discover -s backend/tests/unit -p 'test_*.py'

test-integration:
	python3 -m unittest backend.tests.integration.test_agent_api

test-all: test-unit test-integration
