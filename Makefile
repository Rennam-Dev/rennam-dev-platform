.PHONY: install migrate seed run test lint

install:
	python -m pip install -r requirements-dev.txt

migrate:
	alembic upgrade head

seed:
	python -m app.scripts.seed

run:
	uvicorn app.main:app --reload

test:
	pytest -q

lint:
	ruff check .
