# same verbs in every repo of mine: setup, dev, test, check, fmt, clean
.PHONY: setup dev dev-api dev-web test check fmt clean

setup:
	uv sync
	cd web && npm ci

# api on :8000, ui on :3000, offline stub providers unless .env says otherwise
dev:
	$(MAKE) -j2 dev-api dev-web

dev-api:
	uv run uvicorn paper_trail.api.app:app --app-dir src --reload

dev-web:
	cd web && npm run dev

test:
	uv run pytest -q
	cd web && npm test

# what ci gates on
check: test
	uvx pre-commit run --all-files
	cd web && npm run lint && npm run build

fmt:
	uvx pre-commit run --all-files || true

clean:
	rm -rf .pytest_cache .ruff_cache web/.next
