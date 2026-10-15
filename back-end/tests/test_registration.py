from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models import VerificationCode
from tests.conftest import PROFILE, Outbox, register, unique_phone

API = "/api/v1"


def signup(email: str, code: str, **overrides) -> dict:
    return {
        **PROFILE,
        "phone": unique_phone(),
        "email": email,
        "email_code": code,
        "password": "correct-horse-1",
        "clinic_name": "Sunrise Clinic",
        **overrides,
    }


async def request_code(client: AsyncClient, email: str):
    return await client.post(
        f"{API}/auth/otp", json={"channel": "email", "target": email, "purpose": "register"}
    )


async def test_register_stores_name_parts_phone_and_verified_email(client: AsyncClient) -> None:
    headers = await register(
        client,
        email="Owner@Example.com",
        salutation="Dr.",
        first_name="Simarjeet",
        middle_name="Singh",
        last_name="Arora",
        phone="+91 98765-43210",
    )
    me = (await client.get(f"{API}/auth/me", headers=headers)).json()
    user = me["user"]
    assert user["email"] == "owner@example.com"
    assert (user["salutation"], user["first_name"], user["middle_name"], user["last_name"]) == (
        "Dr.",
        "Simarjeet",
        "Singh",
        "Arora",
    )
    assert user["full_name"] == "Dr. Simarjeet Singh Arora"
    assert user["phone"] == "+919876543210"  # normalised to international format
    assert user["email_verified"] is True and user["phone_verified"] is False
    assert me["memberships"][0]["role"] == "owner"


async def test_middle_name_is_optional(client: AsyncClient) -> None:
    headers = await register(
        client, middle_name="", first_name="Tanishq", last_name="Pawar", salutation="Mr."
    )
    user = (await client.get(f"{API}/auth/me", headers=headers)).json()["user"]
    assert user["middle_name"] is None and user["full_name"] == "Mr. Tanishq Pawar"


async def test_code_email_is_sent(client: AsyncClient, outbox: Outbox) -> None:
    r = await request_code(client, "new@example.com")
    assert r.status_code == 200
    assert r.json()["resend_after_seconds"] == 60 and r.json()["expires_in_minutes"] == 10
    message = outbox.messages[-1]
    assert message.to == "new@example.com"
    assert message.subject == f"{outbox.last_code()} is your Doctoo verification code"


async def test_register_requires_correct_code(client: AsyncClient, outbox: Outbox) -> None:
    await request_code(client, "new@example.com")
    good = outbox.last_code()
    bad = "000000" if good != "000000" else "111111"

    wrong = await client.post(f"{API}/auth/register", json=signup("new@example.com", bad))
    assert wrong.status_code == 400 and "4 attempts left" in wrong.json()["detail"]

    ok = await client.post(f"{API}/auth/register", json=signup("new@example.com", good))
    assert ok.status_code == 201


async def test_code_works_only_once_and_only_for_its_email(
    client: AsyncClient, outbox: Outbox
) -> None:
    await request_code(client, "a@example.com")
    code = outbox.last_code()
    other = await client.post(f"{API}/auth/register", json=signup("b@example.com", code))
    assert other.status_code == 400  # no code was sent to b@example.com

    assert (
        await client.post(f"{API}/auth/register", json=signup("a@example.com", code))
    ).status_code == 201
    again = await client.post(f"{API}/auth/register", json=signup("a@example.com", code))
    assert again.status_code == 409  # account exists now


async def test_too_many_wrong_attempts_locks_the_code(client: AsyncClient, outbox: Outbox) -> None:
    await request_code(client, "new@example.com")
    good = outbox.last_code()
    bad = "000000" if good != "000000" else "111111"
    for _ in range(5):
        await client.post(f"{API}/auth/register", json=signup("new@example.com", bad))
    locked = await client.post(f"{API}/auth/register", json=signup("new@example.com", good))
    assert locked.status_code == 400 and "Too many wrong attempts" in locked.json()["detail"]


async def test_expired_code_is_rejected(
    client: AsyncClient, outbox: Outbox, engine: AsyncEngine
) -> None:
    await request_code(client, "new@example.com")
    async with engine.begin() as conn:
        await conn.execute(
            update(VerificationCode).values(
                expires_at=VerificationCode.expires_at - timedelta(minutes=11)
            )
        )
    r = await client.post(
        f"{API}/auth/register", json=signup("new@example.com", outbox.last_code())
    )
    assert r.status_code == 400 and "expired" in r.json()["detail"]


async def test_resend_cooldown_and_newest_code_only(
    client: AsyncClient, outbox: Outbox, engine: AsyncEngine
) -> None:
    await request_code(client, "new@example.com")
    first = outbox.last_code()
    too_soon = await request_code(client, "new@example.com")
    assert too_soon.status_code == 429 and "wait" in too_soon.json()["detail"]

    async with engine.begin() as conn:  # pretend 2 minutes passed
        await conn.execute(
            update(VerificationCode).values(
                created_at=VerificationCode.created_at - timedelta(minutes=2)
            )
        )
    assert (await request_code(client, "new@example.com")).status_code == 200
    second = outbox.last_code()
    if first != second:
        old = await client.post(f"{API}/auth/register", json=signup("new@example.com", first))
        assert old.status_code == 400  # the older code was replaced
    ok = await client.post(f"{API}/auth/register", json=signup("new@example.com", second))
    assert ok.status_code == 201


async def test_code_not_sent_for_existing_account(client: AsyncClient, outbox: Outbox) -> None:
    await register(client)
    sent_before = len(outbox.messages)
    r = await request_code(client, "OWNER@example.com")
    assert r.status_code == 409 and "already exists" in r.json()["detail"]
    assert len(outbox.messages) == sent_before


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("phone", "9876543210"),  # missing country code
        ("phone", "+91 12345"),  # too short
        ("phone", "+91 1234567890"),  # valid landline-style number, not a mobile
        ("phone", "+91 11 2345 6789"),  # Delhi landline
        ("salutation", "King"),
        ("first_name", ""),
        ("last_name", "Ar0ra"),  # digits not allowed in names
        ("password", "short"),
        ("email_code", "12ab56"),
    ],
)
async def test_invalid_signup_fields(client: AsyncClient, field: str, value: str) -> None:
    r = await client.post(
        f"{API}/auth/register", json=signup("x@example.com", "123456", **{field: value})
    )
    assert r.status_code == 422, f"{field}={value!r} should be rejected"


@pytest.mark.parametrize(
    ("raw", "normalised"),
    [
        ("+91 98765 43210", "+919876543210"),
        ("+1 (415) 555-2671", "+14155552671"),
        ("+44 7400 123456", "+447400123456"),
        ("+971 50 123 4567", "+971501234567"),
    ],
)
async def test_phone_numbers_from_other_countries(
    client: AsyncClient, raw: str, normalised: str
) -> None:
    headers = await register(client, email=f"p{normalised[1:]}@example.com", phone=raw)
    user = (await client.get(f"{API}/auth/me", headers=headers)).json()["user"]
    assert user["phone"] == normalised
