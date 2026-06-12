.PHONY: up down migrate seed test lint logs

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec backend python seed.py

# Тесты гоняются локально (venv создаётся при первом запуске)
test:
	cd backend && { test -d .venv || { python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"; }; } && .venv/bin/pytest -q

lint:
	cd backend && { test -d .venv || { python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"; }; } && .venv/bin/ruff check app tests

logs:
	docker compose logs -f backend bot
