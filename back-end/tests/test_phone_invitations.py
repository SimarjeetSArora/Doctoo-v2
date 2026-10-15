"""Inviting staff by mobile number (the link arrives on WhatsApp)."""

from httpx import AsyncClient

from tests.conftest import PROFILE, Outbox, PhoneOutbox, bearer, register

API = "/api/v1"


def new_staff(**overrides) -> dict:
    return {
        **PROFILE,
        "salutation": "Mr.",
        "first_name": "Tanishq",
        "last_name": "Pawar",
        "phone": "+919000000001",
        **overrides,
    }


async def invite_by_phone(client: AsyncClient, owner: dict, phone: str, role: str = "receptionist"):
    return await client.post(
        f"{API}/invitations", json={"phone": phone, "role": role}, headers=owner
    )


async def email_code(client: AsyncClient, outbox: Outbox, email: str) -> str:
    r = await client.post(
        f"{API}/auth/otp", json={"channel": "email", "target": email, "purpose": "register"}
    )
    assert r.status_code == 200, r.text
    return outbox.last_code()


async def test_invite_needs_exactly_one_contact(client: AsyncClient) -> None:
    owner = await register(client)
    both = await client.post(
        f"{API}/invitations",
        json={"email": "a@example.com", "phone": "+919811122333", "role": "doctor"},
        headers=owner,
    )
    neither = await client.post(f"{API}/invitations", json={"role": "doctor"}, headers=owner)
    landline = await invite_by_phone(client, owner, "+91 11 2345 6789")
    assert both.status_code == neither.status_code == landline.status_code == 422


async def test_new_person_joins_via_sms_invite(
    client: AsyncClient, outbox: Outbox, whatsapp_outbox: PhoneOutbox
) -> None:
    owner = await register(client, clinic_name="Arora's Family Clinic")
    r = await invite_by_phone(client, owner, "+91 98111 22333")
    assert r.status_code == 201
    assert r.json()["phone"] == "+919811122333" and r.json()["email"] is None

    message = whatsapp_outbox.messages[-1]
    assert message.to == "+919811122333"
    assert "Arora's Family Clinic" in message.render() and "/invite?token=" in message.render()
    pending = (await client.get(f"{API}/invitations", headers=owner)).json()
    assert [p["phone"] for p in pending] == ["+919811122333"]

    token = whatsapp_outbox.last_token()
    lookup = (await client.get(f"{API}/invitations/lookup", params={"token": token})).json()
    assert lookup["channel"] == "phone" and lookup["phone"] == "+919811122333"
    assert lookup["needs_name"] and lookup["needs_password"] and lookup["needs_email"]

    # Without an email + code it's refused.
    missing = await client.post(
        f"{API}/invitations/accept",
        json={"token": token, "profile": new_staff(), "password": "staff-pass-123"},
    )
    assert missing.status_code == 422

    code = await email_code(client, outbox, "tanishq@example.com")
    accepted = await client.post(
        f"{API}/invitations/accept",
        json={
            "token": token,
            "profile": new_staff(phone="+919999999999"),  # ignored: the invited number is used
            "password": "staff-pass-123",
            "email": "tanishq@example.com",
            "email_code": code,
        },
    )
    assert accepted.status_code == 200, accepted.text
    user = (await client.get(f"{API}/auth/me", headers=bearer(accepted))).json()["user"]
    assert user["email"] == "tanishq@example.com" and user["phone"] == "+919811122333"
    assert user["email_verified"] and user["phone_verified"]

    # They can now log in with their number and an SMS code.
    await client.post(
        f"{API}/auth/otp",
        json={"channel": "phone", "target": "+919811122333", "purpose": "login"},
    )
    login = await client.post(
        f"{API}/auth/login/otp",
        json={"channel": "phone", "target": "+919811122333", "code": whatsapp_outbox.last_code()},
    )
    assert login.status_code == 200


async def test_sms_invite_with_wrong_email_code(
    client: AsyncClient, outbox: Outbox, whatsapp_outbox: PhoneOutbox
) -> None:
    owner = await register(client)
    await invite_by_phone(client, owner, "+919811122333")
    token = whatsapp_outbox.last_token()
    good = await email_code(client, outbox, "t@example.com")
    r = await client.post(
        f"{API}/invitations/accept",
        json={
            "token": token,
            "profile": new_staff(),
            "password": "staff-pass-123",
            "email": "t@example.com",
            "email_code": "000000" if good != "000000" else "111111",
        },
    )
    assert r.status_code == 400 and "Incorrect verification code" in r.json()["detail"]


async def test_existing_verified_number_joins_directly(
    client: AsyncClient, whatsapp_outbox: PhoneOutbox
) -> None:
    await register(client, email="doc@example.com", phone="+919811122333", clinic_name="Own")
    # Verify the doctor's number by logging in once with an SMS code.
    await client.post(
        f"{API}/auth/otp",
        json={"channel": "phone", "target": "+919811122333", "purpose": "login"},
    )
    await client.post(
        f"{API}/auth/login/otp",
        json={"channel": "phone", "target": "+919811122333", "code": whatsapp_outbox.last_code()},
    )

    owner = await register(client, email="owner2@example.com", clinic_name="Big Hospital")
    await invite_by_phone(client, owner, "+919811122333", role="doctor")
    token = whatsapp_outbox.last_token()
    lookup = (await client.get(f"{API}/invitations/lookup", params={"token": token})).json()
    assert not lookup["needs_name"] and not lookup["needs_password"] and not lookup["needs_email"]

    joined = await client.post(f"{API}/invitations/accept", json={"token": token})
    assert joined.status_code == 200
    me = (await client.get(f"{API}/auth/me", headers=bearer(joined))).json()
    assert sorted(m["clinic_name"] for m in me["memberships"]) == ["Big Hospital", "Own"]


async def test_unverified_number_on_existing_account_is_refused(
    client: AsyncClient, whatsapp_outbox: PhoneOutbox
) -> None:
    # Someone signed up with this number but has never proven they own it.
    await register(client, email="someone@example.com", phone="+919811122333")
    owner = await register(client, email="owner2@example.com", clinic_name="Big Hospital")
    await invite_by_phone(client, owner, "+919811122333")
    token = whatsapp_outbox.last_token()

    lookup = await client.get(f"{API}/invitations/lookup", params={"token": token})
    accept = await client.post(f"{API}/invitations/accept", json={"token": token})
    assert lookup.status_code == accept.status_code == 409
    assert "invite you by email" in lookup.json()["detail"]


async def test_cannot_invite_a_number_already_on_the_team(client: AsyncClient) -> None:
    owner = await register(client, phone="+919811122333")
    r = await invite_by_phone(client, owner, "+919811122333")
    assert r.status_code == 409


async def test_members_list_shows_phone(client: AsyncClient) -> None:
    owner = await register(client, phone="+919811122333")
    members = (await client.get(f"{API}/clinics/current/members", headers=owner)).json()
    assert members[0]["phone"] == "+919811122333"
