from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite+pysqlite:///./rennam-dev.db"
    session_secret: str = "development-only-change-me"
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
    )

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def uses_insecure_session_secret(self) -> bool:
        return self.session_secret == "development-only-change-me"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
