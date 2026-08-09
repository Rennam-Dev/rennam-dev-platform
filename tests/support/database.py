import ipaddress
import os
import re
import socket
from typing import NoReturn
from urllib.parse import SplitResult, unquote, urlsplit

SQLITE_MEMORY_SCHEMES = {"sqlite", "sqlite+pysqlite"}
POSTGRESQL_SCHEMES = {"postgresql", "postgresql+psycopg"}
POSTGRESQL_DEFAULT_PORT = 5432
OFFICIAL_POSTGRESQL_TEST_HOST = "test-db"
OFFICIAL_POSTGRESQL_TEST_PORT = 5432
OFFICIAL_POSTGRESQL_TEST_DATABASE = "rennam_test"
OFFICIAL_POSTGRESQL_TEST_USERNAME = "rennam_test_runner"
OFFICIAL_POSTGRESQL_TEST_PASSWORD = "discardable-test-only"
POSTGRESQL_TARGET_OVERRIDE_ENVIRONMENT_VARIABLES = {
    "PGDATABASE",
    "PGHOST",
    "PGHOSTADDR",
    "PGPORT",
    "PGSERVICE",
    "PGSERVICEFILE",
    "PGUSER",
}
ALLOWED_POSTGRESQL_TEST_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)
PROTECTED_DATABASE_NAME_PARTS = {
    "live",
    "prod",
    "production",
    "stage",
    "staging",
}


def _reject(reason: str) -> NoReturn:
    raise RuntimeError(f"Configuração insegura do banco de testes: {reason}.")


def _postgresql_target(parsed: SplitResult) -> tuple[str, int, str] | None:
    if parsed.scheme.lower() not in POSTGRESQL_SCHEMES:
        return None
    try:
        hostname = parsed.hostname
        parsed_port = parsed.port
    except ValueError:
        return None
    if not hostname:
        return None
    port = POSTGRESQL_DEFAULT_PORT if parsed_port is None else parsed_port

    database_name = unquote(parsed.path.removeprefix("/"))
    if not database_name or "/" in database_name:
        return None
    return hostname.lower(), port, database_name


def _assert_official_postgresql_host_resolves_privately(
    hostname: str, port: int
) -> None:
    try:
        results = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError:
        _reject("o host PostgreSQL descartável não pôde ser resolvido")

    addresses: set[ipaddress.IPv4Address] = set()
    for family, _socket_type, _protocol, _canonical_name, socket_address in results:
        if family != socket.AF_INET:
            _reject("o host PostgreSQL descartável resolveu fora da rede permitida")
        try:
            address = ipaddress.ip_address(socket_address[0])
        except ValueError:
            _reject("o host PostgreSQL descartável retornou endereço inválido")
        if not isinstance(address, ipaddress.IPv4Address):
            _reject("o host PostgreSQL descartável resolveu fora da rede permitida")
        addresses.add(address)

    if not addresses:
        _reject("o host PostgreSQL descartável não retornou endereços")
    if len(addresses) != 1:
        _reject("o host PostgreSQL descartável deve ter um único endereço")
    if any(
        not any(address in network for network in ALLOWED_POSTGRESQL_TEST_NETWORKS)
        for address in addresses
    ):
        _reject("o host PostgreSQL descartável resolveu fora da rede permitida")


def assert_safe_test_database(
    url: str,
    app_env: str,
    normal_database_url: str | None = None,
) -> None:
    """Reject database URLs that are not explicitly safe for destructive tests."""
    if app_env != "test":
        _reject("APP_ENV deve ser test")

    candidate = (url or "").strip()
    if not candidate:
        _reject("TEST_DATABASE_URL deve ser definida")

    normal_candidate = (normal_database_url or "").strip()
    if normal_candidate and candidate == normal_candidate:
        _reject("a URL de teste deve ser diferente da URL normal")

    try:
        parsed = urlsplit(candidate)
    except ValueError:
        _reject("TEST_DATABASE_URL é inválida")

    scheme = parsed.scheme.lower()
    if scheme in SQLITE_MEMORY_SCHEMES:
        if (
            parsed.netloc
            or parsed.path != "/:memory:"
            or parsed.query
            or parsed.fragment
        ):
            _reject("SQLite deve usar exclusivamente memória")
        return

    if scheme not in POSTGRESQL_SCHEMES:
        _reject("backend não permitido")

    if normal_candidate:
        _reject("PostgreSQL de teste exige ausência da URL normal")

    if parsed.query or parsed.fragment:
        _reject("PostgreSQL descartável deve ter host e banco explícitos")

    target = _postgresql_target(parsed)
    if target is None:
        _reject("PostgreSQL descartável deve ter banco explícito")
    hostname, port, database_name = target
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", database_name):
        _reject("nome do banco de testes contém caracteres não permitidos")

    normalized_name = database_name.lower()
    if not normalized_name.endswith("_test"):
        _reject("o nome do banco PostgreSQL deve terminar com _test")

    name_parts = set(re.split(r"[^a-z0-9]+", normalized_name))
    if name_parts & PROTECTED_DATABASE_NAME_PARTS:
        _reject("o nome do banco PostgreSQL é protegido")

    if (
        hostname != OFFICIAL_POSTGRESQL_TEST_HOST
        or port != OFFICIAL_POSTGRESQL_TEST_PORT
        or database_name != OFFICIAL_POSTGRESQL_TEST_DATABASE
        or parsed.username != OFFICIAL_POSTGRESQL_TEST_USERNAME
        or parsed.password != OFFICIAL_POSTGRESQL_TEST_PASSWORD
    ):
        _reject("PostgreSQL deve usar exclusivamente o serviço descartável oficial")

    if POSTGRESQL_TARGET_OVERRIDE_ENVIRONMENT_VARIABLES & os.environ.keys():
        _reject("variáveis libpq não podem alterar o destino PostgreSQL de teste")

    _assert_official_postgresql_host_resolves_privately(hostname, port)
