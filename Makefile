.PHONY: install lint test test-hooks test-smoke test-all clean

install:
	python3 -m pip install -e ".[dev]"

lint:
	python3 -m ruff check src/ tests/
	python3 -m ruff format --check src/ tests/

format:
	python3 -m ruff format src/ tests/
	python3 -m ruff check --fix src/ tests/

test:
	python3 -m pytest tests/framework/test_*.py -v --tb=short

test-hooks:
	bash tests/framework/hooks/run_all_hook_tests.sh

test-replay:
	python3 -m pytest tests/framework/test_replay.py -v --tb=short

test-smoke:
	python3 -m pytest tests/framework/smoke/ -v --tb=short

test-all: test test-hooks test-replay

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .ruff_cache __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
