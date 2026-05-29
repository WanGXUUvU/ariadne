.PHONY: format format-check lint lint-fix test-unit test-integration test-all

BLACK := ./.venv/bin/black
RUFF := ./.venv/bin/ruff

format:
	$(BLACK) agent_prototype

format-check:
	$(BLACK) --check agent_prototype

lint:
	$(RUFF) check agent_prototype

lint-fix:
	$(RUFF) check --fix agent_prototype

test-unit:
	python3 -m unittest discover -s agent_prototype/tests/unit -p 'test_*.py'

test-integration:
	python3 -m unittest agent_prototype.tests.integration.test_agent_api

test-all: test-unit test-integration
