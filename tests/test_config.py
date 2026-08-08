import pytest
from pydantic import ValidationError

from app.core.config import (
    DEFAULT_SESSION_SECRET,
    MIN_SESSION_SECRET_LENGTH,
    Settings,
)

pytestmark = pytest.mark.no_database

VALID_ARGON2_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$ZGlnZXN0"


def production_settings(**overrides: str) -> Settings:
    values = {
        "app_env": "production",
        "database_url": (
            "postgresql+psycopg://app:discardable-password@db/rennam_dev"
        ),
        "session_secret": "s" * MIN_SESSION_SECRET_LENGTH,
        "admin_username": "admin",
        "admin_password_hash": VALID_ARGON2_HASH,
        "site_url": "https://rennam.example/",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize("app_env", ["development", "test", "staging"])
def test_non_production_environments_are_valid(app_env: str) -> None:
    configured = Settings(app_env=app_env, _env_file=None)

    assert configured.app_env == app_env
    assert configured.session_cookie_secure is False


@pytest.mark.parametrize(
    "app_env",
    ["prod", "Production", " production", "production ", "", "unknown"],
)
def test_unknown_environment_is_rejected(app_env: str) -> None:
    with pytest.raises(ValidationError):
        Settings(app_env=app_env, _env_file=None)


def test_development_defaults_remain_available(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in (
        "APP_ENV",
        "DATABASE_URL",
        "SESSION_SECRET",
        "ADMIN_USERNAME",
        "ADMIN_PASSWORD_HASH",
        "SITE_URL",
    ):
        monkeypatch.delenv(variable, raising=False)

    configured = Settings(_env_file=None)

    assert configured.app_env == "development"
    assert configured.database_url == "sqlite+pysqlite:///./rennam-dev.db"
    assert configured.session_secret == DEFAULT_SESSION_SECRET
    assert configured.session_cookie_secure is False


@pytest.mark.parametrize(
    ("overrides", "expected_message"),
    [
        (
            {"session_secret": DEFAULT_SESSION_SECRET},
            "SESSION_SECRET não pode usar o valor de desenvolvimento",
        ),
        (
            {"session_secret": "short"},
            f"SESSION_SECRET deve ter ao menos {MIN_SESSION_SECRET_LENGTH} caracteres",
        ),
        (
            {"admin_password_hash": ""},
            "ADMIN_PASSWORD_HASH deve conter um hash Argon2 válido",
        ),
        (
            {"admin_password_hash": "not-an-argon2-hash"},
            "ADMIN_PASSWORD_HASH deve conter um hash Argon2 válido",
        ),
        (
            {"database_url": "sqlite+pysqlite:///:memory:"},
            "DATABASE_URL deve usar PostgreSQL em production",
        ),
        (
            {"site_url": "http://rennam.example"},
            "SITE_URL deve ser uma URL HTTPS absoluta",
        ),
        (
            {"site_url": "https://rennam.example?preview=1"},
            "SITE_URL deve ser uma URL HTTPS absoluta",
        ),
        (
            {"site_url": "https://rennam.example#fragment"},
            "SITE_URL deve ser uma URL HTTPS absoluta",
        ),
        (
            {"admin_username": ""},
            "ADMIN_USERNAME não pode ser vazio em production",
        ),
        (
            {"admin_username": "   "},
            "ADMIN_USERNAME não pode ser vazio em production",
        ),
    ],
)
def test_unsafe_production_configuration_is_rejected(
    overrides: dict[str, str],
    expected_message: str,
) -> None:
    with pytest.raises(ValidationError, match=expected_message):
        production_settings(**overrides)


def test_valid_production_configuration_is_accepted() -> None:
    configured = production_settings()

    assert configured.app_env == "production"
    assert configured.is_production is True
    assert configured.session_cookie_secure is True
    assert configured.site_url == "https://rennam.example"


def test_validation_error_does_not_expose_secrets() -> None:
    session_secret = "session-secret-that-must-never-appear"
    password_hash = VALID_ARGON2_HASH
    database_password = "database-password-that-must-never-appear"
    database_url = (
        f"postgresql+psycopg://app:{database_password}@db/rennam_dev"
    )

    with pytest.raises(ValidationError) as error:
        production_settings(
            session_secret=session_secret,
            admin_password_hash=password_hash,
            database_url=database_url,
            site_url="http://rennam.example",
        )

    message = str(error.value)
    assert session_secret not in message
    assert password_hash not in message
    assert database_password not in message
    assert database_url not in message
