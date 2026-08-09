import socket

import psycopg
import pytest

from tests.support import database as database_guard
from tests.support.database import assert_safe_test_database

pytestmark = pytest.mark.no_database

OFFICIAL_POSTGRESQL_TEST_URL = (
    "postgresql+psycopg://rennam_test_runner:discardable-test-only"
    "@test-db:5432/rennam_test"
)
GetAddrInfoResult = tuple[int, int, int, str, tuple[str, int]]
GetAddrInfoIPv6Result = tuple[int, int, int, str, tuple[str, int, int, int]]
LIBPQ_TARGET_OVERRIDE_VARIABLES = (
    "PGDATABASE",
    "PGHOST",
    "PGHOSTADDR",
    "PGPORT",
    "PGSERVICE",
    "PGSERVICEFILE",
    "PGUSER",
)


@pytest.fixture(autouse=True)
def clear_libpq_target_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in LIBPQ_TARGET_OVERRIDE_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def resolved_ipv4(*addresses: str) -> list[GetAddrInfoResult]:
    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            (address, 5432),
        )
        for address in addresses
    ]


def resolved_ipv6(address: str) -> list[GetAddrInfoIPv6Result]:
    return [
        (
            socket.AF_INET6,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            (address, 5432, 0, 0),
        )
    ]


@pytest.mark.parametrize(
    "url",
    [
        "sqlite+pysqlite:///:memory:",
        "sqlite:///:memory:",
    ],
)
def test_sqlite_memory_is_accepted_without_dns(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_resolution(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("SQLite em memória não deve resolver hostname")

    monkeypatch.setattr(database_guard.socket, "getaddrinfo", unexpected_resolution)

    assert_safe_test_database(url, "test")


@pytest.mark.parametrize("address", ["10.20.0.2", "172.28.0.2", "192.168.50.2"])
def test_official_postgresql_is_accepted_with_private_resolution(
    address: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, int]] = []

    def private_resolution(
        hostname: str, port: int, *, type: int
    ) -> list[GetAddrInfoResult]:
        calls.append((hostname, port))
        assert type == socket.SOCK_STREAM
        return resolved_ipv4(address)

    monkeypatch.setattr(database_guard.socket, "getaddrinfo", private_resolution)

    assert_safe_test_database(OFFICIAL_POSTGRESQL_TEST_URL, "test")

    assert calls == [("test-db", 5432)]


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
        ("mysql://tester:discardable@db/rennam_test", "test"),
        (
            "postgresql+psycopg://rennam_test_runner:discardable-test-only"
            "@test-db:5432/rennam",
            "test",
        ),
        ("postgresql+psycopg:///rennam_test", "test"),
        (
            f"{OFFICIAL_POSTGRESQL_TEST_URL}?host=database-remoto.exemplo.com",
            "test",
        ),
        (
            "postgresql+psycopg://rennam_test_runner:discardable-test-only"
            "@test-db:5432/production_test",
            "test",
        ),
        (
            "postgresql+psycopg://rennam_test_runner:discardable-test-only"
            "@test-db:5432/staging_test",
            "test",
        ),
        (
            "postgresql+psycopg://rennam_test_runner:discardable-test-only"
            "@database-remoto.exemplo.com:5432/rennam_test",
            "test",
        ),
        (
            "postgresql+psycopg://rennam_test_runner:discardable-test-only"
            "@8.8.8.8:5432/rennam_test",
            "test",
        ),
        (
            "postgresql+psycopg://rennam_test_runner:discardable-test-only"
            "@10.20.0.50:5432/rennam_test",
            "test",
        ),
        (
            "postgresql+psycopg://rennam_test_runner:discardable-test-only"
            "@staging-db.internal:5432/rennam_test",
            "test",
        ),
        (
            "postgresql+psycopg://rennam_test_runner:discardable-test-only"
            "@localhost:5432/rennam_test",
            "test",
        ),
        (
            "postgresql+psycopg://rennam_test_runner:discardable-test-only"
            "@127.0.0.1:5432/rennam_test",
            "test",
        ),
        (
            "postgresql+psycopg://other:discardable-test-only"
            "@test-db:5432/rennam_test",
            "test",
        ),
        (
            "postgresql+psycopg://rennam_test_runner:other"
            "@test-db:5432/rennam_test",
            "test",
        ),
        (
            "postgresql+psycopg://rennam_test_runner:discardable-test-only"
            "@test-db:5433/rennam_test",
            "test",
        ),
        (
            "postgresql+psycopg://rennam_test_runner:discardable-test-only"
            "@test-db:0/rennam_test",
            "test",
        ),
        (
            "postgresql+psycopg://rennam_test_runner:discardable-test-only"
            "@test-db:5432/other_test",
            "test",
        ),
    ],
)
def test_unsafe_test_database_is_rejected_before_dns(
    url: str, app_env: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_resolution(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("configuração já negada não deve consultar DNS")

    monkeypatch.setattr(database_guard.socket, "getaddrinfo", unexpected_resolution)

    with pytest.raises(RuntimeError):
        assert_safe_test_database(url, app_env)


@pytest.mark.parametrize(
    "addresses",
    [
        ("8.8.8.8",),
        ("172.28.0.2", "8.8.8.8"),
        ("172.28.0.2", "192.168.50.2"),
        ("127.0.0.1",),
        ("169.254.10.20",),
    ],
)
def test_official_hostname_resolving_outside_allowed_networks_is_rejected(
    addresses: tuple[str, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        database_guard.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: resolved_ipv4(*addresses),
    )

    with pytest.raises(RuntimeError):
        assert_safe_test_database(OFFICIAL_POSTGRESQL_TEST_URL, "test")


def test_official_hostname_resolving_to_ipv6_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        database_guard.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: resolved_ipv6("2001:4860:4860::8888"),
    )

    with pytest.raises(RuntimeError):
        assert_safe_test_database(OFFICIAL_POSTGRESQL_TEST_URL, "test")


def test_official_hostname_resolution_failure_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed_resolution(*_args: object, **_kwargs: object) -> None:
        raise socket.gaierror("simulated DNS failure")

    monkeypatch.setattr(database_guard.socket, "getaddrinfo", failed_resolution)

    with pytest.raises(RuntimeError):
        assert_safe_test_database(OFFICIAL_POSTGRESQL_TEST_URL, "test")


def test_official_hostname_empty_resolution_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        database_guard.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [],
    )

    with pytest.raises(RuntimeError):
        assert_safe_test_database(OFFICIAL_POSTGRESQL_TEST_URL, "test")


def test_normal_database_url_is_rejected() -> None:
    with pytest.raises(RuntimeError):
        assert_safe_test_database(
            OFFICIAL_POSTGRESQL_TEST_URL,
            "test",
            normal_database_url=OFFICIAL_POSTGRESQL_TEST_URL,
        )


def test_normal_database_alias_is_rejected_before_dns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    normal_url = "postgresql://other:credentials@TEST-DB/rennam_test"

    def unexpected_resolution(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("o mesmo destino normal deve ser negado antes do DNS")

    monkeypatch.setattr(database_guard.socket, "getaddrinfo", unexpected_resolution)

    with pytest.raises(RuntimeError):
        assert_safe_test_database(
            OFFICIAL_POSTGRESQL_TEST_URL,
            "test",
            normal_database_url=normal_url,
        )


def test_any_normal_database_url_blocks_postgresql_before_dns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    normal_url = "postgresql://normal:credentials@unrelated-db/other_database"

    def unexpected_resolution(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("PostgreSQL com URL normal presente deve ser negado")

    monkeypatch.setattr(database_guard.socket, "getaddrinfo", unexpected_resolution)

    with pytest.raises(RuntimeError):
        assert_safe_test_database(
            OFFICIAL_POSTGRESQL_TEST_URL,
            "test",
            normal_database_url=normal_url,
        )


@pytest.mark.parametrize(
    "variable",
    LIBPQ_TARGET_OVERRIDE_VARIABLES,
)
def test_libpq_target_override_is_rejected_before_dns(
    variable: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_resolution(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("override libpq deve ser negado antes do DNS")

    monkeypatch.setenv(variable, "unsafe-override")
    monkeypatch.setattr(database_guard.socket, "getaddrinfo", unexpected_resolution)

    with pytest.raises(RuntimeError):
        assert_safe_test_database(OFFICIAL_POSTGRESQL_TEST_URL, "test")


def test_denied_attempt_never_opens_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection_attempts = 0

    def public_resolution(
        *_args: object, **_kwargs: object
    ) -> list[GetAddrInfoResult]:
        return resolved_ipv4("8.8.8.8")

    def forbidden_connection(*_args: object, **_kwargs: object) -> None:
        nonlocal connection_attempts
        connection_attempts += 1
        raise AssertionError("a guarda não deve abrir conexão TCP")

    monkeypatch.setattr(database_guard.socket, "getaddrinfo", public_resolution)
    monkeypatch.setattr(
        database_guard.socket,
        "create_connection",
        forbidden_connection,
    )
    monkeypatch.setattr(psycopg, "connect", forbidden_connection)

    with pytest.raises(RuntimeError):
        assert_safe_test_database(OFFICIAL_POSTGRESQL_TEST_URL, "test")

    assert connection_attempts == 0


def test_error_message_does_not_expose_credentials_or_url() -> None:
    password = "sensitive-password"
    url = (
        f"postgresql+psycopg://admin:{password}"
        "@database-remoto.exemplo.com/production_test"
    )

    with pytest.raises(RuntimeError) as error:
        assert_safe_test_database(url, "test")

    message = str(error.value)
    assert password not in message
    assert url not in message
