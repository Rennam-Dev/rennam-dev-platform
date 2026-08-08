import re
from urllib.parse import unquote, urlsplit

SQLITE_MEMORY_SCHEMES = {"sqlite", "sqlite+pysqlite"}
POSTGRESQL_SCHEMES = {"postgresql", "postgresql+psycopg"}
PROTECTED_DATABASE_NAME_PARTS = {
    "live",
    "prod",
    "production",
    "stage",
    "staging",
}


def _reject(reason: str) -> None:
    raise RuntimeError(f"Configuração insegura do banco de testes: {reason}.")


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

    if not parsed.hostname or parsed.query or parsed.fragment:
        _reject("PostgreSQL descartável deve ter host e banco explícitos")

    database_name = unquote(parsed.path.removeprefix("/"))
    if not database_name or "/" in database_name:
        _reject("PostgreSQL descartável deve ter banco explícito")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", database_name):
        _reject("nome do banco de testes contém caracteres não permitidos")

    normalized_name = database_name.lower()
    if not normalized_name.endswith("_test"):
        _reject("o nome do banco PostgreSQL deve terminar com _test")

    name_parts = set(re.split(r"[^a-z0-9]+", normalized_name))
    if name_parts & PROTECTED_DATABASE_NAME_PARTS:
        _reject("o nome do banco PostgreSQL é protegido")
