from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables / the .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Doctoo API"
    environment: str = "development"  # development | staging | production

    # postgresql+asyncpg://user:password@host:port/database
    database_url: str

    # Used to sign login tokens (JWT). Must be long and random in production.
    secret_key: str
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    password_reset_expire_minutes: int = 60
    invitation_expire_days: int = 7

    # Frontend URLs allowed to call this API from the browser
    cors_origins: list[str] = ["http://localhost:5173"]
    # Used to build links in emails (password reset, invitations)
    frontend_url: str = "http://localhost:5173"

    # "console" prints emails in the backend terminal (development).
    email_backend: str = "console"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
