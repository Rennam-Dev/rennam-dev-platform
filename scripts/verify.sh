#!/bin/sh
set -eu

guard_database() {
    python -c 'import os; from tests.support.database import assert_safe_test_database; assert_safe_test_database(os.environ.get("TEST_DATABASE_URL", ""), os.environ.get("APP_ENV", ""), normal_database_url=os.environ.get("NORMAL_DATABASE_URL"))'
}

NORMAL_DATABASE_URL="${DATABASE_URL:-}"
export NORMAL_DATABASE_URL
unset DATABASE_URL

guard_database
ruff check --no-cache .

guard_database
pytest -q -p no:cacheprovider tests/test_database_guard.py tests/test_config.py

guard_database
pytest -q -p no:cacheprovider

guard_database
export DATABASE_URL="$TEST_DATABASE_URL"

guard_database
alembic current

guard_database
alembic heads

guard_database
alembic upgrade head

guard_database
alembic current

guard_database
alembic check

guard_database
alembic downgrade base

guard_database
alembic upgrade head

guard_database
alembic current
