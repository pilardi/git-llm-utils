.PHONY: format check-formatting check-code check tests verify install update dist clean-dist

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
	uv run pytest

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
	uv dist

binary: install
	@echo "Building binary ..."
	pyinstaller git-llm-utils.spec

clean-dist:
	@echo "Removing dist ..."
	rm -rf dist/

clean: clean-dist
	@echo "Removing env"
	rm -rf .venv/
