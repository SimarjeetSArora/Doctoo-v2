"""SMS templates and the MSG91 sender (tested against a fake MSG91 server)."""

import json

import httpx
import pytest

from app.core.config import get_settings
from app.services.sms import (
    TEMPLATE_TEXT,
    Msg91Error,
    Msg91SmsSender,
    SmsMessage,
    SmsTemplate,
)


def msg91_settings(**overrides):
    return get_settings().model_copy(
        update={
            "sms_backend": "msg91",
            "msg91_auth_key": "test-auth-key",
            "msg91_login_template_id": "tmpl-login",
            "msg91_invitation_template_id": "tmpl-invite",
            **overrides,
        }
    )


def fake_msg91(captured: list, status: int = 200, reply: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(status, json=reply or {"type": "success", "message": "queued"})

    return httpx.MockTransport(handler)


def login_sms() -> SmsMessage:
    return SmsMessage(
        to="+919876543210",
        template=SmsTemplate.LOGIN_CODE,
        params={"code": "482913", "minutes": "10"},
    )


def test_every_template_variable_is_filled() -> None:
    text = login_sms().render()
    assert text == "482913 is your Doctoo login code. Valid 10 min. Do not share it with anyone."
    for template in SmsTemplate:
        assert template in TEMPLATE_TEXT


async def test_msg91_request_format() -> None:
    captured: list[httpx.Request] = []
    sender = Msg91SmsSender(msg91_settings(), transport=fake_msg91(captured))
    await sender.send(login_sms())

    request = captured[0]
    assert request.method == "POST"
    assert str(request.url) == "https://control.msg91.com/api/v5/flow"
    assert request.headers["authkey"] == "test-auth-key"
    body = json.loads(request.content)
    assert body == {
        "template_id": "tmpl-login",
        "short_url": "1",
        "recipients": [{"mobiles": "919876543210", "code": "482913", "minutes": "10"}],
    }


async def test_msg91_trims_variables_to_dlt_limit() -> None:
    captured: list[httpx.Request] = []
    sender = Msg91SmsSender(msg91_settings(), transport=fake_msg91(captured))
    await sender.send(
        SmsMessage(
            to="+919876543210",
            template=SmsTemplate.INVITATION,
            params={"clinic": "The Very Long Name Multispeciality Family Clinic", "role": "doctor"},
        )
    )
    recipient = json.loads(captured[0].content)["recipients"][0]
    assert json.loads(captured[0].content)["template_id"] == "tmpl-invite"
    assert len(recipient["clinic"]) == 30


@pytest.mark.parametrize(
    ("status", "reply"),
    [(401, {"type": "error", "message": "Authentication failure"}), (200, {"type": "error"})],
)
async def test_msg91_errors_are_raised(status: int, reply: dict) -> None:
    sender = Msg91SmsSender(msg91_settings(), transport=fake_msg91([], status, reply))
    with pytest.raises(Msg91Error):
        await sender.send(login_sms())


async def test_msg91_missing_configuration() -> None:
    with pytest.raises(Msg91Error, match="MSG91_AUTH_KEY"):
        await Msg91SmsSender(msg91_settings(msg91_auth_key=""), transport=fake_msg91([])).send(
            login_sms()
        )
    with pytest.raises(Msg91Error, match="template ID"):
        await Msg91SmsSender(
            msg91_settings(msg91_login_template_id=""), transport=fake_msg91([])
        ).send(login_sms())
