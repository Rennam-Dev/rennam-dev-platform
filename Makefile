TEST_COMPOSE = docker compose --env-file /dev/null \
	--project-name rennam-dev-test -f compose.test.yml

.PHONY: install migrate seed run test lint verify test-db-up test-db-down

install:
	python -m pip install -r requirements-dev.txt

migrate:
	alembic upgrade head

seed:
	python -m app.scripts.seed

run:
	uvicorn app.main:app --reload

test:
	pytest -q -m no_database

lint:
	ruff check .

verify:
	@set -eu; \
	trap '$(TEST_COMPOSE) down --volumes --remove-orphans' EXIT INT TERM; \
	$(TEST_COMPOSE) run --build --rm verify

test-db-up:
	$(TEST_COMPOSE) up --detach --wait test-db

test-db-down:
	$(TEST_COMPOSE) down --volumes --remove-orphans
