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

    # SMS: "mailpit" shows texts in the dev inbox at localhost:8025; "console" prints them in the
    # backend terminal; "msg91" sends real SMS (needs the MSG91 settings below).
    sms_backend: Literal["mailpit", "console", "msg91"] = "mailpit"
    sms_mailpit_host: str = "localhost"
    sms_mailpit_port: int = 1025

    # MSG91 (India). Template IDs come from MSG91's SMS > Templates page, after DLT approval.
    msg91_auth_key: str = ""
    msg91_login_template_id: str = ""
    msg91_invitation_template_id: str = ""
    msg91_short_urls: bool = True  # shorten links to fit DLT's 30-character variable limit
    msg91_base_url: str = "https://control.msg91.com/api/v5"

    # WhatsApp: same backend choices as SMS ("mailpit" | "console" | "msg91").
    whatsapp_backend: Literal["mailpit", "console", "msg91"] = "mailpit"
    msg91_whatsapp_number: str = ""  # your WhatsApp Business number in MSG91, e.g. 919876543210
    msg91_whatsapp_login_template: str = "doctoo_login_code"
    msg91_whatsapp_invitation_template: str = "doctoo_invitation"
    msg91_whatsapp_language: str = "en"
    msg91_whatsapp_namespace: str = ""  # only if MSG91's sample request includes one
    msg91_whatsapp_url: str = (
        "https://api.msg91.com/api/v5/whatsapp/whatsapp-outbound-message/bulk/"
    )
    # How invitations to a mobile number are delivered.
    phone_invite_via: Literal["whatsapp", "sms"] = "whatsapp"

    @property
    def whatsapp_ready(self) -> bool:
        if self.whatsapp_backend != "msg91":
            return True
        return bool(self.msg91_auth_key and self.msg91_whatsapp_number)

    @property
    def sms_ready(self) -> bool:
        if self.sms_backend != "msg91":
            return True
        return bool(self.msg91_auth_key and self.msg91_login_template_id)

    def phone_code_channels(self) -> list[str]:
        """Ways a login code can reach a phone right now (WhatsApp first)."""
        return [
            c for c, ready in (("whatsapp", self.whatsapp_ready), ("sms", self.sms_ready)) if ready
        ]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
