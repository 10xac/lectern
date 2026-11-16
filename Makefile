# lectern: every target is safe to re-run.
SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help

PNPM ?= corepack pnpm
# Run pnpm from inside frontend/ so corepack picks the version pinned in its package.json.
FE := cd frontend && $(PNPM)
DB ?= lectern.db

.PHONY: help install dev seed backend frontend check lint format typecheck test fe-lint fe-typecheck fe-test \
	loc forbidden pptx demo clean

help: ## list the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install: ## install Python (uv) and frontend (pnpm) dependencies from the lockfiles
	uv sync --frozen
	$(FE) install --frozen-lockfile

dev: ## run the API on :8000 and the web app on :5173 (seeds the sample decks on first run)
	@test -f $(DB) || LECTERN_DB=$(DB) uv run lectern seed decks
	@trap 'kill 0' INT TERM EXIT; LECTERN_DB=$(DB) uv run lectern serve --port 8000 & ($(FE) dev) & wait

seed: ## ingest the decks in decks/ into $(DB)
	LECTERN_DB=$(DB) uv run lectern seed decks

check: lint typecheck test fe-lint fe-typecheck fe-test loc forbidden ## everything CI runs

lint: ## ruff lint + format check
	uv run ruff check backend scripts
	uv run ruff format --check backend scripts

format: ## ruff format + autofix
	uv run ruff format backend scripts
	uv run ruff check --fix backend scripts

typecheck: ## mypy (strict) on the backend
	uv run mypy

test: ## backend tests
	uv run pytest -q

fe-lint: ## eslint
	$(FE) lint

fe-typecheck: ## tsc
	$(FE) typecheck

fe-test: ## vitest + Testing Library
	$(FE) test

loc: ## the size budget
	uv run python scripts/loc_budget.py

forbidden: ## no answer-key paths or canary markers
	uv run python scripts/check_forbidden_paths.py

pptx: ## rebuild the sample .pptx files from scripts/make_sample_pptx.py
	uv run python scripts/make_sample_pptx.py

demo: ## an AI client builds the v0.2 demo deck and its DNA over MCP, then asks it questions
	LECTERN_DB=demo.db LECTERN_BLOBS=demo-blobs uv run python scripts/demo.py

clean: ## remove caches and the local database
	rm -rf .mypy_cache .ruff_cache .pytest_cache frontend/dist $(DB) lectern-blobs demo.db demo-blobs
	find . -name __pycache__ -type d -prune -not -path './.venv/*' -exec rm -rf {} +
