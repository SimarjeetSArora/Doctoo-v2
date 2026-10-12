from functools import lru_cache
from typing import Literal

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

    # Email delivery: "smtp" sends through the SMTP server below; "console" just prints
    # emails in the backend terminal.
    email_backend: Literal["smtp", "console"] = "smtp"
    # Empty = use smtp_username (required for Gmail, which only sends as the logged-in account)
    email_from_address: str = "no-reply@doctoo.local"
    email_from_name: str = "Doctoo"

    # SMTP server. Defaults point at Mailpit from docker-compose (dev inbox: localhost:8025).
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    # "starttls" for port 587, "ssl" for port 465, "none" for local Mailpit
    smtp_security: Literal["starttls", "ssl", "none"] = "none"
    smtp_timeout_seconds: float = 15

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
