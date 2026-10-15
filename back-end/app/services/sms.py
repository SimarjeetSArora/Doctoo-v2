"""Text messages (login codes, invitation links).

India's DLT rules only allow SMS that match pre-approved templates, so messages are sent as
"template + values" rather than free text. Backends:

- "mailpit" (development): each SMS appears in the Mailpit inbox (http://localhost:8025) as an
  email addressed to sms+<number>@doctoo.local.
- "console": prints SMS in the backend terminal.
- "msg91": sends real SMS through MSG91's Flow API, using the template IDs from .env.
"""

import enum
import logging
from dataclasses import dataclass, field
from email.message import EmailMessage as MimeMessage
from typing import Protocol

import aiosmtplib
import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger("doctoo.sms")

# DLT allows at most 30 characters per template variable.
_DLT_VARIABLE_MAX = 30


class SmsTemplate(enum.StrEnum):
    LOGIN_CODE = "login_code"
    INVITATION = "invitation"


# The wording registered on DLT/MSG91 must match these. ##name## marks a variable.
TEMPLATE_TEXT: dict[SmsTemplate, str] = {
    SmsTemplate.LOGIN_CODE: (
        "##code## is your Doctoo login code. Valid ##minutes## min. Do not share it with anyone."
    ),
    SmsTemplate.INVITATION: (
        "##inviter## invited you to join ##clinic## on Doctoo as a ##role##. "
        "Accept within ##days## days: ##link##"
    ),
}


@dataclass
class SmsMessage:
    to: str  # E.164, e.g. +919876543210
    template: SmsTemplate
    params: dict[str, str] = field(default_factory=dict)

    def render(self) -> str:
        """The text as the recipient sees it."""
        text = TEMPLATE_TEXT[self.template]
        for name, value in self.params.items():
            text = text.replace(f"##{name}##", value)
        return text


class SmsSender(Protocol):
    async def send(self, message: SmsMessage) -> None: ...


class ConsoleSmsSender:
    """Prints SMS in the backend terminal."""

    async def send(self, message: SmsMessage) -> None:
        print(f"\n{'=' * 70}\nSMS to: {message.to}\n\n{message.render()}\n{'=' * 70}\n", flush=True)


class MailpitSmsSender:
    """Development: shows each SMS in the Mailpit inbox (needs `docker compose up -d`)."""

    def __init__(self, host: str, port: int) -> None:
        self.host, self.port = host, port

    async def send(self, message: SmsMessage) -> None:
        mime = MimeMessage()
        mime["From"] = "Doctoo SMS <sms@doctoo.local>"
        mime["To"] = f"sms+{message.to.lstrip('+')}@doctoo.local"
        mime["Subject"] = f"SMS to {message.to}"
        mime.set_content(message.render())
        await aiosmtplib.send(mime, hostname=self.host, port=self.port, timeout=10)


class Msg91Error(Exception):
    pass


class Msg91SmsSender:
    """Real SMS through MSG91's Flow API (one approved template per message type)."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.transport = transport  # tests pass a fake transport

    def template_id(self, template: SmsTemplate) -> str:
        template_id = {
            SmsTemplate.LOGIN_CODE: self.settings.msg91_login_template_id,
            SmsTemplate.INVITATION: self.settings.msg91_invitation_template_id,
        }[template]
        if not template_id:
            raise Msg91Error(f"No MSG91 template ID configured for {template!r}")
        return template_id

    def payload(self, message: SmsMessage) -> dict:
        recipient = {"mobiles": message.to.lstrip("+")}  # MSG91 wants 919876543210
        for name, value in message.params.items():
            recipient[name] = value[:_DLT_VARIABLE_MAX]
        return {
            "template_id": self.template_id(message.template),
            # MSG91 can shorten links so they fit DLT's per-variable limit.
            "short_url": "1" if self.settings.msg91_short_urls else "0",
            "recipients": [recipient],
        }

    async def send(self, message: SmsMessage) -> None:
        if not self.settings.msg91_auth_key:
            raise Msg91Error("MSG91_AUTH_KEY is not set")
        async with httpx.AsyncClient(
            base_url=self.settings.msg91_base_url, timeout=15, transport=self.transport
        ) as client:
            response = await client.post(
                "/flow",
                json=self.payload(message),
                headers={"authkey": self.settings.msg91_auth_key, "accept": "application/json"},
            )
        try:
            result = response.json()
        except ValueError:
            result = {}
        if response.status_code >= 400 or result.get("type") != "success":
            raise Msg91Error(f"MSG91 rejected the SMS ({response.status_code}): {response.text}")


def get_sms_sender() -> SmsSender:
    """FastAPI dependency: the configured SMS backend."""
    settings = get_settings()
    if settings.sms_backend == "console":
        return ConsoleSmsSender()
    if settings.sms_backend == "msg91":
        return Msg91SmsSender(settings)
    return MailpitSmsSender(settings.sms_mailpit_host, settings.sms_mailpit_port)


async def deliver_sms(sender: SmsSender, message: SmsMessage) -> None:
    """Sends in the background. Failures are logged, never shown to users."""
    try:
        await sender.send(message)
    except Exception:
        logger.exception("Failed to send SMS (%s) to %s", message.template, message.to)
