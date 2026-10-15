"""WhatsApp templates and the MSG91 WhatsApp sender (tested against a fake MSG91 server)."""

import json

import httpx
import pytest

from app.core.config import get_settings
from app.services.whatsapp import (
    Msg91WhatsAppError,
    Msg91WhatsAppSender,
    WhatsAppMessage,
    WhatsAppTemplate,
)


def settings(**overrides):
    return get_settings().model_copy(
        update={
            "whatsapp_backend": "msg91",
            "msg91_auth_key": "test-auth-key",
            "msg91_whatsapp_number": "+919000000000",
            **overrides,
        }
    )


def fake_msg91(captured: list, status: int = 200, reply: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(status, json=reply or {"status": "success", "hasError": False})

    return httpx.MockTransport(handler)


def test_rendered_text() -> None:
    code = WhatsAppMessage("+919876543210", WhatsAppTemplate.LOGIN_CODE, {"code": "482913"})
    assert code.render() == (
        "*482913* is your verification code. For your security, do not share this code."
    )
    invite = WhatsAppMessage(
        "+919876543210",
        WhatsAppTemplate.INVITATION,
        {
            "inviter": "Dr. A",
            "clinic": "Sunrise",
            "role": "doctor",
            "days": "7",
            "link": "https://x",
        },
    )
    assert invite.render() == (
        "Dr. A invited you to join Sunrise on Doctoo as a doctor. Accept within 7 days: https://x"
    )


async def test_login_code_request_has_copy_code_button() -> None:
    captured: list[httpx.Request] = []
    sender = Msg91WhatsAppSender(settings(), transport=fake_msg91(captured))
    await sender.send(
        WhatsAppMessage("+919876543210", WhatsAppTemplate.LOGIN_CODE, {"code": "482913"})
    )

    request = captured[0]
    assert str(request.url).startswith("https://api.msg91.com/api/v5/whatsapp/")
    assert request.headers["authkey"] == "test-auth-key"
    body = json.loads(request.content)
    assert body["integrated_number"] == "919000000000"
    assert body["content_type"] == "template"
    template = body["payload"]["template"]
    assert template["name"] == "doctoo_login_code"
    assert template["language"] == {"code": "en", "policy": "deterministic"}
    assert template["to_and_components"] == [
        {
            "to": ["919876543210"],
            "components": {
                "body_1": {"type": "text", "value": "482913"},
                "button_1": {"subtype": "url", "type": "text", "value": "482913"},
            },
        }
    ]


async def test_invitation_request_fills_variables_in_order() -> None:
    captured: list[httpx.Request] = []
    sender = Msg91WhatsAppSender(settings(), transport=fake_msg91(captured))
    await sender.send(
        WhatsAppMessage(
            "+919876543210",
            WhatsAppTemplate.INVITATION,
            {"inviter": "Dr. A", "clinic": "Sunrise", "role": "doctor", "days": "7", "link": "L"},
        )
    )
    components = json.loads(captured[0].content)["payload"]["template"]["to_and_components"][0][
        "components"
    ]
    assert [components[f"body_{i}"]["value"] for i in range(1, 6)] == [
        "Dr. A",
        "Sunrise",
        "doctor",
        "7",
        "L",
    ]
    assert "button_1" not in components


@pytest.mark.parametrize(
    ("status", "reply"),
    [(401, {"status": "fail"}), (200, {"status": "fail", "hasError": True})],
)
async def test_errors_are_raised(status: int, reply: dict) -> None:
    sender = Msg91WhatsAppSender(settings(), transport=fake_msg91([], status, reply))
    with pytest.raises(Msg91WhatsAppError):
        await sender.send(
            WhatsAppMessage("+919876543210", WhatsAppTemplate.LOGIN_CODE, {"code": "1"})
        )


async def test_missing_configuration() -> None:
    sender = Msg91WhatsAppSender(settings(msg91_whatsapp_number=""), transport=fake_msg91([]))
    with pytest.raises(Msg91WhatsAppError, match="MSG91_WHATSAPP_NUMBER"):
        await sender.send(
            WhatsAppMessage("+919876543210", WhatsAppTemplate.LOGIN_CODE, {"code": "1"})
        )
