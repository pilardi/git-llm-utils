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
	uv run pytest

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

.ONESHELL:
test/dist/git-llm-utils: dist/git-llm-utils 
	@uv run python tests/test_server.py &
	SERVER_ID=$$!
	@WORK_DIR=$$(pwd)
	@TEMP_DIR=$$(mktemp -d)
	cd $${TEMP_DIR} && git init . && echo "test" > test.txt && git add test.txt
	$${WORK_DIR}/dist/git-llm-utils status --api-url http://127.0.0.1:8001 --model openai/test --api-key test > status.out
	$${WORK_DIR}/dist/git-llm-utils generate --api-url http://127.0.0.1:8001 --model openai/test --api-key test --no-manual > generate.out
	$${WORK_DIR}/dist/git-llm-utils generate --api-url http://127.0.0.1:8001 --model openai/test --api-key test --no-manual --with-comments > generate-comments.out
	kill $${SERVER_ID}


clean-dist:
	@echo "Removing dist ..."
	rm -rf dist/

clean: clean-dist
	@echo "Removing env"
	rm -rf .venv/
