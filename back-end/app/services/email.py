import logging
from dataclasses import dataclass
from typing import Protocol

from app.core.config import get_settings

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


def get_email_sender() -> EmailSender:
    """FastAPI dependency. Real providers (Resend, Brevo, SES) plug in here later."""
    backend = get_settings().email_backend
    if backend == "console":
        return ConsoleEmailSender()
    raise RuntimeError(f"Unknown EMAIL_BACKEND: {backend!r}")
