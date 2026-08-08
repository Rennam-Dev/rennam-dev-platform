import os

import pytest
from fastapi.testclient import TestClient

from tests.support.database import assert_safe_test_database

NORMAL_DATABASE_URL = os.environ.get("DATABASE_URL")
os.environ["APP_ENV"] = "test"
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+pysqlite:///:memory:",
)
assert_safe_test_database(
    TEST_DATABASE_URL,
    os.environ["APP_ENV"],
    normal_database_url=NORMAL_DATABASE_URL,
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.core.config import settings  # noqa: E402
from app.core.database import Base, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.routes.admin import login_rate_limiter  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database(request: pytest.FixtureRequest):
    login_rate_limiter.reset()
    if request.node.get_closest_marker("no_database"):
        yield
        login_rate_limiter.reset()
        return

    assert_safe_test_database(
        TEST_DATABASE_URL,
        settings.app_env,
        normal_database_url=NORMAL_DATABASE_URL,
    )
    Base.metadata.drop_all(bind=engine)
    assert_safe_test_database(
        TEST_DATABASE_URL,
        settings.app_env,
        normal_database_url=NORMAL_DATABASE_URL,
    )
    Base.metadata.create_all(bind=engine)
    settings.admin_password_hash = hash_password("test-password")
    yield
    login_rate_limiter.reset()
    assert_safe_test_database(
        TEST_DATABASE_URL,
        settings.app_env,
        normal_database_url=NORMAL_DATABASE_URL,
    )
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
