import logging
import uuid

import httpx
import pytest

from app.core.config import Settings, get_settings
from app.services import email as email_module
from app.services.email import EmailMessage, SmtpEmailSender, deliver

MAILPIT_API = "http://localhost:8025/api/v1"


def smtp_settings(**overrides) -> Settings:
    return get_settings().model_copy(update={"email_backend": "smtp", **overrides})


def test_message_headers() -> None:
    sender = SmtpEmailSender(
        smtp_settings(email_from_address="hello@doctoo.in", email_from_name="Doctoo Clinic")
    )
    mime = sender.build(EmailMessage(to="doc@example.com", subject="Hi", body="Body text"))
    assert mime["From"] == "Doctoo Clinic <hello@doctoo.in>"
    assert mime["To"] == "doc@example.com"
    assert mime["Subject"] == "Hi"
    assert mime["Message-ID"].endswith("@doctoo.in>")
    assert mime.get_content().strip() == "Body text"


def test_from_address_defaults_to_smtp_username() -> None:
    """Gmail only sends as the logged-in account, so an empty from-address uses the username."""
    sender = SmtpEmailSender(
        smtp_settings(email_from_address="", smtp_username="clinic.owner@gmail.com")
    )
    mime = sender.build(EmailMessage(to="x@example.com", subject="S", body="B"))
    assert mime["From"] == "Doctoo <clinic.owner@gmail.com>"


@pytest.mark.parametrize(
    ("security", "use_tls", "start_tls"),
    [("ssl", True, False), ("starttls", False, True), ("none", False, False)],
)
async def test_smtp_security_modes(monkeypatch, security, use_tls, start_tls) -> None:
    calls = []

    async def fake_send(message, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(email_module.aiosmtplib, "send", fake_send)
    sender = SmtpEmailSender(
        smtp_settings(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user",
            smtp_password="secret",
            smtp_security=security,
        )
    )
    await sender.send(EmailMessage(to="a@example.com", subject="S", body="B"))

    kwargs = calls[0]
    assert (kwargs["hostname"], kwargs["port"]) == ("smtp.example.com", 587)
    assert (kwargs["username"], kwargs["password"]) == ("user", "secret")
    assert (kwargs["use_tls"], kwargs["start_tls"]) == (use_tls, start_tls)


async def test_delivery_failure_is_logged_not_raised(caplog) -> None:
    class BrokenSender:
        async def send(self, message: EmailMessage) -> None:
            raise ConnectionRefusedError("SMTP server down")

    with caplog.at_level(logging.ERROR, logger="doctoo.email"):
        await deliver(BrokenSender(), EmailMessage(to="a@example.com", subject="Reset", body="x"))
    assert "Failed to send email 'Reset' to a@example.com" in caplog.text


async def test_real_send_through_mailpit() -> None:
    """Integration test: needs `docker compose up -d` (Mailpit). Skipped otherwise."""
    try:
        httpx.get(f"{MAILPIT_API}/messages", timeout=2).raise_for_status()
    except httpx.HTTPError:
        pytest.skip("Mailpit is not running")

    subject = f"Doctoo test {uuid.uuid4()}"
    sender = SmtpEmailSender(
        smtp_settings(
            smtp_host="localhost",
            smtp_port=1025,
            smtp_security="none",
            smtp_username="",
            smtp_password="",
            email_from_address="no-reply@doctoo.local",
        )
    )
    await sender.send(EmailMessage(to="test@example.com", subject=subject, body="Hello"))

    found = httpx.get(f"{MAILPIT_API}/search", params={"query": f'subject:"{subject}"'}).json()
    assert found["messages_count"] == 1
    assert found["messages"][0]["To"][0]["Address"] == "test@example.com"
    httpx.request(  # clean up the test email
        "DELETE", f"{MAILPIT_API}/messages", json={"IDs": [found["messages"][0]["ID"]]}
    )
