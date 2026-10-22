"""WhatsApp messages (login codes, invitation links; prescriptions later).

WhatsApp only allows business-initiated messages that use templates approved by Meta, so
messages are sent as "template + values". Backends:

- "mailpit" (development): each message appears in the Mailpit inbox (http://localhost:8025) as
  an email addressed to whatsapp+<number>@doctoo.local.
- "console": prints messages in the backend terminal.
- "msg91": sends real WhatsApp messages through MSG91 (an official Meta partner).
"""

import enum
import logging
from dataclasses import dataclass, field
from email.message import EmailMessage as MimeMessage
from typing import Protocol

import aiosmtplib
import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger("doctoo.whatsapp")


class WhatsAppTemplate(enum.StrEnum):
    LOGIN_CODE = "login_code"  # Meta "Authentication" template with a copy-code button
    INVITATION = "invitation"  # Meta "Utility" template
    APPOINTMENT_CONFIRMED = "appointment_confirmed"  # Meta "Utility" template


# Text as approved by Meta ({{1}}, {{2}}… are filled in order from VARIABLES below).
TEMPLATE_TEXT: dict[WhatsAppTemplate, str] = {
    WhatsAppTemplate.LOGIN_CODE: (
        "*{{1}}* is your verification code. For your security, do not share this code."
    ),
    WhatsAppTemplate.INVITATION: (
        "{{1}} invited you to join {{2}} on Doctoo as a {{3}}. Accept within {{4}} days: {{5}}"
    ),
    WhatsAppTemplate.APPOINTMENT_CONFIRMED: (
        "Hi {{1}}, your appointment with {{2}} at {{3}} is confirmed for {{4}}. "
        "Please arrive 10 minutes early."
    ),
}
VARIABLES: dict[WhatsAppTemplate, list[str]] = {
    WhatsAppTemplate.LOGIN_CODE: ["code"],
    WhatsAppTemplate.INVITATION: ["inviter", "clinic", "role", "days", "link"],
    WhatsAppTemplate.APPOINTMENT_CONFIRMED: ["patient", "doctor", "clinic", "when"],
}


@dataclass
class WhatsAppMessage:
    to: str  # E.164, e.g. +919876543210
    template: WhatsAppTemplate
    params: dict[str, str] = field(default_factory=dict)

    def values(self) -> list[str]:
        return [self.params[name] for name in VARIABLES[self.template]]

    def render(self) -> str:
        """The text as the recipient sees it."""
        text = TEMPLATE_TEXT[self.template]
        for position, value in enumerate(self.values(), start=1):
            text = text.replace(f"{{{{{position}}}}}", value)
        return text


class WhatsAppSender(Protocol):
    async def send(self, message: WhatsAppMessage) -> None: ...


class ConsoleWhatsAppSender:
    async def send(self, message: WhatsAppMessage) -> None:
        line = "=" * 70
        print(f"\n{line}\nWHATSAPP to: {message.to}\n\n{message.render()}\n{line}\n", flush=True)


class MailpitWhatsAppSender:
    """Development: shows each WhatsApp message in the Mailpit inbox."""

    def __init__(self, host: str, port: int) -> None:
        self.host, self.port = host, port

    async def send(self, message: WhatsAppMessage) -> None:
        mime = MimeMessage()
        mime["From"] = "Doctoo WhatsApp <whatsapp@doctoo.local>"
        mime["To"] = f"whatsapp+{message.to.lstrip('+')}@doctoo.local"
        mime["Subject"] = f"WhatsApp to {message.to}"
        mime.set_content(message.render())
        await aiosmtplib.send(mime, hostname=self.host, port=self.port, timeout=10)


class Msg91WhatsAppError(Exception):
    pass


class Msg91WhatsAppSender:
    """Real WhatsApp messages through MSG91's template API."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.transport = transport  # tests pass a fake transport

    def template_name(self, template: WhatsAppTemplate) -> str:
        s = self.settings
        name = {
            WhatsAppTemplate.LOGIN_CODE: s.msg91_whatsapp_login_template,
            WhatsAppTemplate.INVITATION: s.msg91_whatsapp_invitation_template,
            WhatsAppTemplate.APPOINTMENT_CONFIRMED: s.msg91_whatsapp_appointment_template,
        }[template]
        if not name:
            raise Msg91WhatsAppError(f"No MSG91 WhatsApp template configured for {template!r}")
        return name

    def payload(self, message: WhatsAppMessage) -> dict:
        components: dict[str, dict] = {
            f"body_{position}": {"type": "text", "value": value}
            for position, value in enumerate(message.values(), start=1)
        }
        if message.template == WhatsAppTemplate.LOGIN_CODE:
            # Authentication templates carry the code again for the "Copy code" button.
            components["button_1"] = {
                "subtype": "url",
                "type": "text",
                "value": message.values()[0],
            }
        template: dict = {
            "name": self.template_name(message.template),
            "language": {"code": self.settings.msg91_whatsapp_language, "policy": "deterministic"},
            "to_and_components": [{"to": [message.to.lstrip("+")], "components": components}],
        }
        if self.settings.msg91_whatsapp_namespace:
            template["namespace"] = self.settings.msg91_whatsapp_namespace
        return {
            "integrated_number": self.settings.msg91_whatsapp_number.lstrip("+"),
            "content_type": "template",
            "payload": {"messaging_product": "whatsapp", "type": "template", "template": template},
        }

    async def send(self, message: WhatsAppMessage) -> None:
        s = self.settings
        if not s.msg91_auth_key or not s.msg91_whatsapp_number:
            raise Msg91WhatsAppError("MSG91_AUTH_KEY and MSG91_WHATSAPP_NUMBER must be set")
        async with httpx.AsyncClient(timeout=15, transport=self.transport) as client:
            response = await client.post(
                s.msg91_whatsapp_url,
                json=self.payload(message),
                headers={"authkey": s.msg91_auth_key, "accept": "application/json"},
            )
        try:
            result = response.json()
        except ValueError:
            result = {}
        if response.status_code >= 400 or result.get("status") == "fail" or result.get("hasError"):
            raise Msg91WhatsAppError(
                f"MSG91 rejected the WhatsApp message ({response.status_code}): {response.text}"
            )


def get_whatsapp_sender() -> WhatsAppSender:
    """FastAPI dependency: the configured WhatsApp backend."""
    settings = get_settings()
    if settings.whatsapp_backend == "console":
        return ConsoleWhatsAppSender()
    if settings.whatsapp_backend == "msg91":
        return Msg91WhatsAppSender(settings)
    return MailpitWhatsAppSender(settings.sms_mailpit_host, settings.sms_mailpit_port)


async def deliver_whatsapp(sender: WhatsAppSender, message: WhatsAppMessage) -> None:
    """Sends in the background. Failures are logged, never shown to users."""
    try:
        await sender.send(message)
    except Exception:
        logger.exception("Failed to send WhatsApp (%s) to %s", message.template, message.to)
