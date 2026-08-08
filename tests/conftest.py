import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import Base, engine
from app.core.security import hash_password
from app.main import app


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    settings.admin_password_hash = hash_password("test-password")
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
