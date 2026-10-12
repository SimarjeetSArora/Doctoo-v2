import logging
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from email.utils import formataddr, make_msgid
from typing import Protocol

import aiosmtplib

from app.core.config import Settings, get_settings

logger = logging.getLogger("doctoo.email")


@dataclass
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Development: prints emails to the backend terminal instead of sending them."""

    async def send(self, message: EmailMessage) -> None:
        line = "=" * 70
        header = f"EMAIL to: {message.to}\nSubject: {message.subject}"
        print(f"\n{line}\n{header}\n\n{message.body}\n{line}\n", flush=True)


class SmtpEmailSender:
    """Sends email over SMTP: Mailpit in development, a real provider in production."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def from_address(self) -> str:
        # Gmail only sends "as" the logged-in account, so default to the SMTP username.
        return self.settings.email_from_address or self.settings.smtp_username

    def build(self, message: EmailMessage) -> MimeMessage:
        mime = MimeMessage()
        mime["From"] = formataddr((self.settings.email_from_name, self.from_address))
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime["Message-ID"] = make_msgid(domain=self.from_address.split("@")[-1])
        mime.set_content(message.body)
        return mime

    async def send(self, message: EmailMessage) -> None:
        s = self.settings
        if not self.from_address:
            raise RuntimeError("No sender address: set SMTP_USERNAME or EMAIL_FROM_ADDRESS in .env")
        await aiosmtplib.send(
            self.build(message),
            hostname=s.smtp_host,
            port=s.smtp_port,
            username=s.smtp_username or None,
            password=s.smtp_password or None,
            use_tls=s.smtp_security == "ssl",  # encrypted from the start (port 465)
            start_tls=s.smtp_security == "starttls",  # upgrade to encryption (port 587)
            timeout=s.smtp_timeout_seconds,
        )


def get_email_sender() -> EmailSender:
    """FastAPI dependency: the configured email backend."""
    settings = get_settings()
    if settings.email_backend == "console":
        return ConsoleEmailSender()
    return SmtpEmailSender(settings)


async def deliver(sender: EmailSender, message: EmailMessage) -> None:
    """Sends in the background (after the response). Failures are logged, never shown to users."""
    try:
        await sender.send(message)
    except Exception:
        logger.exception("Failed to send email %r to %s", message.subject, message.to)
