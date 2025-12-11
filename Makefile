.PHONY: format check-formatting check-code check tests test-src-dist test-bin-dist test-dist verify install update dist clean-dist

DISTRIBUTION_TESTS = tests/test_generate.py

format:
	@echo "Formatting Python files ..."
	uv run ruff format  .

check-formatting:
	@echo "== Running formatting verification =="
	uv run ruff format --diff .

check-code:
	@echo "== Running code verification =="
	uv run ruff check .

check: check-formatting check-code
	@echo "Code verification complete"

tests:
	@echo "== Running python tests =="
	uv run pytest -m "not integration"

test-src-dist: dist
	@echo "== Running python tests over source dist =="
	uv run --isolated --no-project --with dist/*.tar.gz pytest $(DISTRIBUTION_TESTS)

test-bin-dist: dist
	@echo "== Running python tests over bin dist =="
	uv run --isolated --no-project --with dist/*.whl pytest $(DISTRIBUTION_TESTS)

test-dist: test-src-dist test-bin-dist
	@echo "Distribution tests complete"

verify: check tests
	@echo "Verification complete"

install:
	@echo "Installing dependencies ..."
	uv sync --locked --all-extras --dev

update:
	@echo "Updading dependencies ..."
	uv lock

dist: install
	@echo "Building package ..."
	uv build

dist/git-llm-utils: install
	@echo "Building binary ..."
	pyinstaller git-llm-utils.spec

tests/integration: dist/git-llm-utils
	uv run pytest -m "integration"

clean-dist:
	@echo "Removing dist ..."
	rm -rf dist/

clean: clean-dist
	@echo "Removing env"
	rm -rf .venv/
