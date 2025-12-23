.PHONY: format check-formatting check-code check verify install update tests tests/src tests/bin tests/dist/src tests/dist/bin tests/dist/git-llm-utils

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

tests:
	@echo "== Running python tests =="
	uv run pytest ${PY_TESTS_FLAGS} -m "not integration"

tests/src: dist
	@echo "== Running python tests over source dist =="
	uv run --isolated --no-project --with dist/*.tar.gz pytest ${PY_TESTS_FLAGS} $(DISTRIBUTION_TESTS)

tests/bin: dist
	@echo "== Running python tests over bin dist =="
	uv run --isolated --no-project --with dist/*.whl pytest ${PY_TESTS_FLAGS} $(DISTRIBUTION_TESTS)

tests/dist/src: dist
	@echo "== Running integration tests over src dist =="
	uv run pytest ${PY_TESTS_FLAGS} -m "integration" --cmd "uv run --isolated --no-project --with `find $$PWD/dist -type f -name '*.tar.gz'` git-llm-utils"

tests/dist/bin: dist
	@echo "== Running integration tests over bin dist =="
	uv run pytest ${PY_TESTS_FLAGS} -m "integration" --cmd "uv run --isolated --no-project --with `find $$PWD/dist -type f -name '*.whl'` git-llm-utils"

tests/dist/git-llm-utils: dist/git-llm-utils
	@echo "== Running integration tests over executable dist =="
	uv run pytest ${PY_TESTS_FLAGS} -m "integration"

clean/dist:
	@echo "Removing dist ..."
	rm -rf dist/

clean: clean/dist
	@echo "Removing env"
	rm -rf .venv/
