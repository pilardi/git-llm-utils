.PHONY: format verify install update dist tests clean-dist

format:
	@echo "Formatting Python files ..."
	uv run ruff format  .

verify:
	@echo "Testing Python files ..."
	uv run ruff format --diff . && uv run ruff check .

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

tests:
	@echo "Running tests with Pytest..."
	uv run pytest

clean-dist:
	@echo "Removing dist ..."
	rm -rf dist/

clean: clean-dist
	@echo "Removing env"
	rm -rf .venv/
