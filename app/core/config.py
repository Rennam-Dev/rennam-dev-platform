import re
from functools import lru_cache
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SESSION_SECRET = "development-only-change-me"
MIN_SESSION_SECRET_LENGTH = 32
POSTGRESQL_SCHEMES = {"postgresql", "postgresql+psycopg"}
ARGON2_HASH_PATTERN = re.compile(
    r"^\$argon2(?:id|i|d)\$v=19\$m=\d+,t=\d+,p=\d+"
    r"\$[A-Za-z0-9+/]+={0,2}\$[A-Za-z0-9+/]+={0,2}$"
)
HOSTNAME_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)"
    r"(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*$"
)
AppEnvironment = Literal["development", "test", "staging", "production"]
DEPLOYED_ENVIRONMENTS: frozenset[AppEnvironment] = frozenset(
    {"staging", "production"}
)


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
    admin_login_max_failures: int = 5
    admin_login_window_seconds: int = 10 * 60
    admin_login_max_clients: int = 10_000
    allowed_hosts: str = "127.0.0.1,localhost,testserver"
    forwarded_allow_ips: str = "127.0.0.1"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    @field_validator("allowed_hosts")
    @classmethod
    def validate_allowed_hosts(cls, value: str) -> str:
        hosts = [item.strip().lower() for item in value.split(",")]
        if not hosts or any(not host for host in hosts):
            raise ValueError("ALLOWED_HOSTS deve conter hosts explícitos")
        for host in hosts:
            if host == "*" or host.startswith("*."):
                raise ValueError("ALLOWED_HOSTS não permite wildcard")
            try:
                parsed_host = ip_address(host)
            except ValueError as error:
                if not HOSTNAME_PATTERN.fullmatch(host):
                    raise ValueError(
                        "ALLOWED_HOSTS contém host inválido"
                    ) from error
            else:
                if parsed_host.version == 6:
                    raise ValueError(
                        "ALLOWED_HOSTS não suporta IPv6 literal"
                    )
        return ",".join(dict.fromkeys(hosts))

    @field_validator("forwarded_allow_ips")
    @classmethod
    def validate_forwarded_allow_ips(cls, value: str) -> str:
        networks = [item.strip() for item in value.split(",")]
        if not networks or any(not network for network in networks):
            raise ValueError(
                "FORWARDED_ALLOW_IPS deve conter IPs ou redes explícitas"
            )
        if "*" in networks:
            raise ValueError("FORWARDED_ALLOW_IPS não permite confiança global")
        for network in networks:
            if "/" in network:
                try:
                    parsed_network = ip_network(network)
                except ValueError as error:
                    raise ValueError(
                        "FORWARDED_ALLOW_IPS contém IP ou rede inválida"
                    ) from error
                if parsed_network.prefixlen == 0:
                    raise ValueError(
                        "FORWARDED_ALLOW_IPS não permite confiança global"
                    )
                continue
            try:
                ip_address(network)
            except ValueError as error:
                raise ValueError(
                    "FORWARDED_ALLOW_IPS contém IP ou rede inválida"
                ) from error
        return ",".join(dict.fromkeys(networks))

    @model_validator(mode="after")
    def validate_deployed_configuration(self) -> Self:
        if self.admin_login_max_failures < 1:
            raise ValueError("ADMIN_LOGIN_MAX_FAILURES deve ser maior que zero")
        if self.admin_login_window_seconds < 1:
            raise ValueError("ADMIN_LOGIN_WINDOW_SECONDS deve ser maior que zero")
        if self.admin_login_max_clients < 1:
            raise ValueError("ADMIN_LOGIN_MAX_CLIENTS deve ser maior que zero")

        if not self.requires_secure_configuration:
            return self

        normalized_session_secret = self.session_secret.strip()
        if normalized_session_secret != self.session_secret:
            raise ValueError(
                "SESSION_SECRET não pode conter caracteres em branco nas "
                "bordas em staging/production"
            )
        if normalized_session_secret == DEFAULT_SESSION_SECRET:
            raise ValueError("SESSION_SECRET não pode usar o valor de desenvolvimento")
        if (
            not normalized_session_secret
            or len(normalized_session_secret) < MIN_SESSION_SECRET_LENGTH
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
                "DATABASE_URL deve usar PostgreSQL em staging/production"
            ) from error
        if database_url.scheme.lower() not in POSTGRESQL_SCHEMES:
            raise ValueError(
                "DATABASE_URL deve usar PostgreSQL em staging/production"
            )

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
            raise ValueError(
                "ADMIN_USERNAME não pode ser vazio em staging/production"
            )

        if site_url.hostname not in self.allowed_host_list:
            raise ValueError(
                "ALLOWED_HOSTS deve incluir o host de SITE_URL em "
                "staging/production"
            )

        self.admin_username = self.admin_username.strip()
        self.site_url = self.site_url.rstrip("/")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def requires_secure_configuration(self) -> bool:
        return self.app_env in DEPLOYED_ENVIRONMENTS

    @property
    def session_cookie_secure(self) -> bool:
        return self.requires_secure_configuration

    @property
    def allowed_host_list(self) -> list[str]:
        return self.allowed_hosts.split(",")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
