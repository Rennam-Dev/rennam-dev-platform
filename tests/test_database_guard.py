import pytest

from tests.support.database import assert_safe_test_database

pytestmark = pytest.mark.no_database


@pytest.mark.parametrize(
    "url",
    [
        "sqlite+pysqlite:///:memory:",
        "sqlite:///:memory:",
        "postgresql+psycopg://tester:discardable@db/rennam_dev_test",
        "postgresql://tester:discardable@localhost/rennam_dev_test",
    ],
)
def test_safe_test_database_is_accepted(url: str) -> None:
    assert_safe_test_database(url, "test")


@pytest.mark.parametrize(
    ("url", "app_env"),
    [
        ("sqlite+pysqlite:///:memory:", ""),
        ("sqlite+pysqlite:///:memory:", "development"),
        ("sqlite+pysqlite:///:memory:", "staging"),
        ("sqlite+pysqlite:///:memory:", "production"),
        ("sqlite+pysqlite:///:memory:", "prod"),
        ("sqlite+pysqlite:///:memory:", "unknown"),
        ("", "test"),
        ("sqlite+pysqlite:///test.db", "test"),
        ("sqlite:///tmp/test.db", "test"),
        ("mysql://tester:discardable@db/rennam_dev_test", "test"),
        ("postgresql+psycopg://tester:discardable@db/rennam_dev", "test"),
        ("postgresql+psycopg:///rennam_dev_test", "test"),
        (
            "postgresql+psycopg://tester:discardable@db/rennam_dev_test?host=other",
            "test",
        ),
        ("postgresql+psycopg://tester:discardable@db/production_test", "test"),
        ("postgresql+psycopg://tester:discardable@db/staging_test", "test"),
        ("postgresql+psycopg://tester:discardable@db/prod_test", "test"),
    ],
)
def test_unsafe_test_database_is_rejected(url: str, app_env: str) -> None:
    with pytest.raises(RuntimeError):
        assert_safe_test_database(url, app_env)


def test_normal_database_url_is_rejected() -> None:
    url = "postgresql+psycopg://tester:discardable@db/rennam_dev_test"

    with pytest.raises(RuntimeError):
        assert_safe_test_database(url, "test", normal_database_url=url)


def test_error_message_does_not_expose_credentials_or_url() -> None:
    password = "sensitive-password"
    url = f"postgresql+psycopg://admin:{password}@db/production_test"

    with pytest.raises(RuntimeError) as error:
        assert_safe_test_database(url, "test")

    message = str(error.value)
    assert password not in message
    assert url not in message
