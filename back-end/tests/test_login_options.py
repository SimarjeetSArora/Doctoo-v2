"""Logging in with email or mobile number, using a password or a one-time code."""

from httpx import AsyncClient

from tests.conftest import PROFILE, Outbox, PhoneOutbox, SmsOutbox, bearer, register

API = "/api/v1"
PASSWORD = "correct-horse-1"


async def me(client: AsyncClient, response) -> dict:
    return (await client.get(f"{API}/auth/me", headers=bearer(response))).json()["user"]


async def request_login_code(
    client: AsyncClient, channel: str, target: str, delivery: str = "whatsapp"
):
    return await client.post(
        f"{API}/auth/otp",
        json={"channel": channel, "target": target, "purpose": "login", "delivery": delivery},
    )


# ---------- Password ----------


async def test_password_login_with_mobile_number(client: AsyncClient) -> None:
    await register(client, email="doc@example.com", phone="+91 98111 22333")
    ok = await client.post(
        f"{API}/auth/login", json={"identifier": "+91 98111 22333", "password": PASSWORD}
    )
    assert ok.status_code == 200
    assert (await me(client, ok))["email"] == "doc@example.com"

    compact = await client.post(
        f"{API}/auth/login", json={"identifier": "+919811122333", "password": PASSWORD}
    )
    assert compact.status_code == 200


async def test_password_login_failures_are_generic(client: AsyncClient) -> None:
    await register(client, phone="+919811122333")
    attempts = [
        {"identifier": "+919811122333", "password": "wrong-password"},  # wrong password
        {"identifier": "+919800000000", "password": PASSWORD},  # unknown number
        {"identifier": "9811122333", "password": PASSWORD},  # no country code
    ]
    for body in attempts:
        r = await client.post(f"{API}/auth/login", json=body)
        assert r.status_code == 401, body
        assert r.json()["detail"] == "Incorrect mobile number or password"


# ---------- One-time code ----------


async def test_login_with_email_code(client: AsyncClient, outbox: Outbox) -> None:
    await register(client, email="doc@example.com")
    r = await request_login_code(client, "email", "Doc@Example.com")
    assert r.status_code == 200
    assert outbox.messages[-1].to == "doc@example.com"
    assert "login code" in outbox.messages[-1].subject

    ok = await client.post(
        f"{API}/auth/login/otp",
        json={"channel": "email", "target": "doc@example.com", "code": outbox.last_code()},
    )
    assert ok.status_code == 200
    assert (await me(client, ok))["email"] == "doc@example.com"


async def test_login_with_sms_code_verifies_the_number(
    client: AsyncClient, sms_outbox: SmsOutbox
) -> None:
    await register(client, phone="+919811122333")
    r = await request_login_code(client, "phone", "+91 98111 22333", delivery="sms")
    assert r.status_code == 200 and r.json()["detail"].endswith("by SMS")
    sms = sms_outbox.messages[-1]
    assert sms.to == "+919811122333" and "login code" in sms.render()

    ok = await client.post(
        f"{API}/auth/login/otp",
        json={"channel": "phone", "target": "+919811122333", "code": sms_outbox.last_code()},
    )
    assert ok.status_code == 200
    user = await me(client, ok)
    assert user["phone"] == "+919811122333" and user["phone_verified"] is True


async def test_login_code_for_unknown_account_looks_the_same_but_sends_nothing(
    client: AsyncClient, outbox: Outbox, sms_outbox: SmsOutbox
) -> None:
    await register(client, email="doc@example.com")
    known = await request_login_code(client, "email", "doc@example.com")
    unknown = await request_login_code(client, "email", "ghost@example.com")
    assert known.status_code == unknown.status_code == 200
    assert "If this email belongs to a Doctoo account" in unknown.json()["detail"]
    assert all(m.to != "ghost@example.com" for m in outbox.messages)

    r = await request_login_code(client, "phone", "+919800000000")
    assert r.status_code == 200 and sms_outbox.messages == []

    guess = await client.post(
        f"{API}/auth/login/otp",
        json={"channel": "email", "target": "ghost@example.com", "code": "123456"},
    )
    assert guess.status_code in (400, 401)


async def test_login_code_rules(client: AsyncClient, outbox: Outbox) -> None:
    await register(client, email="doc@example.com")
    await request_login_code(client, "email", "doc@example.com")
    good = outbox.last_code()
    bad = "000000" if good != "000000" else "111111"
    body = {"channel": "email", "target": "doc@example.com"}

    wrong = await client.post(f"{API}/auth/login/otp", json={**body, "code": bad})
    assert wrong.status_code == 400 and "Incorrect verification code" in wrong.json()["detail"]
    assert (
        await client.post(f"{API}/auth/login/otp", json={**body, "code": good})
    ).status_code == 200
    reused = await client.post(f"{API}/auth/login/otp", json={**body, "code": good})
    assert reused.status_code == 400  # single use

    too_soon = await request_login_code(client, "email", "doc@example.com")
    assert too_soon.status_code == 429


async def test_signup_code_by_phone_is_not_offered_yet(client: AsyncClient) -> None:
    r = await client.post(
        f"{API}/auth/otp",
        json={"channel": "phone", "target": "+919811122333", "purpose": "register"},
    )
    assert r.status_code == 422


async def test_invalid_targets_are_rejected(client: AsyncClient) -> None:
    for channel, target in [("email", "not-an-email"), ("phone", "12345"), ("phone", "98111")]:
        r = await request_login_code(client, channel, target)
        assert r.status_code == 422, (channel, target)


async def test_mobile_number_must_be_unique(client: AsyncClient, outbox: Outbox) -> None:
    await register(client, email="a@example.com", phone="+919811122333")
    sent = await client.post(
        f"{API}/auth/otp",
        json={"channel": "email", "target": "b@example.com", "purpose": "register"},
    )
    assert sent.status_code == 200
    code = outbox.last_code()
    dup = await client.post(
        f"{API}/auth/register",
        json={
            **PROFILE,
            "phone": "+91 98111 22333",
            "email": "b@example.com",
            "email_code": code,
            "password": PASSWORD,
            "clinic_name": "Other Clinic",
        },
    )
    assert dup.status_code == 409 and "mobile number is already registered" in dup.json()["detail"]


async def test_login_with_whatsapp_code(client: AsyncClient, whatsapp_outbox: PhoneOutbox) -> None:
    await register(client, phone="+919811122333")
    r = await request_login_code(client, "phone", "+919811122333", delivery="whatsapp")
    assert r.status_code == 200 and r.json()["detail"].endswith("on WhatsApp")
    message = whatsapp_outbox.messages[-1]
    assert message.to == "+919811122333" and "verification code" in message.render()
    ok = await client.post(
        f"{API}/auth/login/otp",
        json={"channel": "phone", "target": "+919811122333", "code": whatsapp_outbox.last_code()},
    )
    assert ok.status_code == 200


async def test_auth_options_and_unavailable_channel(client: AsyncClient, monkeypatch) -> None:
    from app.core.config import get_settings

    r = await client.get(f"{API}/auth/options")
    assert r.json() == {"phone_code_channels": ["whatsapp", "sms"]}

    # Production before DLT: MSG91 SMS isn't configured, WhatsApp is.
    settings = get_settings()
    monkeypatch.setattr(settings, "sms_backend", "msg91")
    monkeypatch.setattr(settings, "whatsapp_backend", "msg91")
    monkeypatch.setattr(settings, "msg91_auth_key", "key")
    monkeypatch.setattr(settings, "msg91_whatsapp_number", "919000000000")
    monkeypatch.setattr(settings, "msg91_login_template_id", "")
    assert (await client.get(f"{API}/auth/options")).json() == {"phone_code_channels": ["whatsapp"]}

    await register(client, phone="+919811122333")
    sms = await request_login_code(client, "phone", "+919811122333", delivery="sms")
    assert sms.status_code == 400
    assert sms.json()["detail"] == "Codes by SMS aren't available yet. Please use WhatsApp instead."
