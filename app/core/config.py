import re
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SESSION_SECRET = "development-only-change-me"
MIN_SESSION_SECRET_LENGTH = 32
POSTGRESQL_SCHEMES = {"postgresql", "postgresql+psycopg"}
ARGON2_HASH_PATTERN = re.compile(
    r"^\$argon2(?:id|i|d)\$v=19\$m=\d+,t=\d+,p=\d+"
    r"\$[A-Za-z0-9+/]+={0,2}\$[A-Za-z0-9+/]+={0,2}$"
)
AppEnvironment = Literal["development", "test", "staging", "production"]


class Settings(BaseSettings):
    app_env: AppEnvironment = "development"
    database_url: str = "sqlite+pysqlite:///./rennam-dev.db"
    session_secret: str = DEFAULT_SESSION_SECRET
    admin_username: str = "rennam"
    admin_password_hash: str = ""
    site_url: str = "http://127.0.0.1:8000"
    github_url: str = "https://github.com/"
    linkedin_url: str = "https://www.linkedin.com/"
    contact_email: str = "eu@rennam.dev"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    @model_validator(mode="after")
    def validate_production_configuration(self) -> Self:
        if self.app_env != "production":
            return self

        if self.session_secret == DEFAULT_SESSION_SECRET:
            raise ValueError("SESSION_SECRET não pode usar o valor de desenvolvimento")
        if (
            not self.session_secret.strip()
            or len(self.session_secret) < MIN_SESSION_SECRET_LENGTH
        ):
            message = (
                "SESSION_SECRET deve ter ao menos "
                f"{MIN_SESSION_SECRET_LENGTH} caracteres"
            )
            raise ValueError(message)
        if not self.admin_password_hash or not ARGON2_HASH_PATTERN.fullmatch(
            self.admin_password_hash
        ):
            raise ValueError("ADMIN_PASSWORD_HASH deve conter um hash Argon2 válido")

        try:
            database_url = urlsplit(self.database_url)
        except ValueError as error:
            raise ValueError(
                "DATABASE_URL deve usar PostgreSQL em production"
            ) from error
        if database_url.scheme.lower() not in POSTGRESQL_SCHEMES:
            raise ValueError("DATABASE_URL deve usar PostgreSQL em production")

        try:
            site_url = urlsplit(self.site_url)
        except ValueError as error:
            raise ValueError("SITE_URL deve ser uma URL HTTPS absoluta") from error
        if (
            site_url.scheme != "https"
            or not site_url.netloc
            or not site_url.hostname
            or any(character.isspace() for character in self.site_url)
            or site_url.username
            or site_url.password
            or site_url.query
            or site_url.fragment
        ):
            raise ValueError(
                "SITE_URL deve ser uma URL HTTPS absoluta, sem credenciais, "
                "query ou fragment"
            )

        if not self.admin_username.strip():
            raise ValueError("ADMIN_USERNAME não pode ser vazio em production")

        self.admin_username = self.admin_username.strip()
        self.site_url = self.site_url.rstrip("/")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def session_cookie_secure(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
