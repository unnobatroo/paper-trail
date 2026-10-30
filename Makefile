# same verbs in every repo of mine: setup, dev, test, check, fmt, clean
.PHONY: setup dev test check fmt clean

setup:
	uv sync

# api + review ui on :8000, offline stub providers unless .env says otherwise
dev:
	uv run uvicorn paper_trail.ui.main:app --app-dir src --reload

test:
	uv run pytest -q

# what ci gates on
check: test
	uvx pre-commit run --all-files

fmt:
	uvx pre-commit run --all-files || true

clean:
	rm -rf .pytest_cache .ruff_cache .nicegui
