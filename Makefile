# same verbs in every repo of mine: setup, dev, test, check, fmt, clean
.PHONY: setup dev frontend-dev frontend-build api-types test check fmt clean

setup:
	uv sync

# the api on :8000, offline stub providers unless .env says otherwise. It serves the built
# review app too (make frontend-build); run make frontend-dev beside it for hot reload
dev:
	uv run uvicorn paper_trail.api.app:app --app-dir src --reload

frontend-dev:
	npm --prefix frontend install
	npm --prefix frontend run dev

frontend-build:
	npm --prefix frontend ci
	npm --prefix frontend run build

# regenerate the frontend's API types after changing the api
api-types:
	uv run python scripts/ops/dump_openapi.py frontend/openapi.json
	npm --prefix frontend run gen:api

test:
	uv run pytest -q

# what ci gates on
check: test
	uvx pre-commit run --all-files
	npm --prefix frontend ci
	npm --prefix frontend run lint
	npm --prefix frontend test
	npm --prefix frontend run build

fmt:
	uvx pre-commit run --all-files || true

clean:
	rm -rf .pytest_cache .ruff_cache frontend/dist
