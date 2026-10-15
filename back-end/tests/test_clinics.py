from httpx import AsyncClient

from tests.conftest import PROFILE, Outbox, bearer, register, unique_phone

API = "/api/v1"


def staff() -> dict:
    return {
        **PROFILE,
        "salutation": "Ms.",
        "first_name": "New",
        "last_name": "Staff",
        "phone": unique_phone(),
    }


async def invite_and_accept(
    client: AsyncClient, outbox: Outbox, owner: dict[str, str], email: str, role: str
) -> dict[str, str]:
    r = await client.post(f"{API}/invitations", json={"email": email, "role": role}, headers=owner)
    assert r.status_code == 201, r.text
    accepted = await client.post(
        f"{API}/invitations/accept",
        json={"token": outbox.last_token(), "profile": staff(), "password": "staff-pass-123"},
    )
    assert accepted.status_code == 200, accepted.text
    return {**bearer(accepted), "X-Clinic-Id": owner["X-Clinic-Id"]}


async def test_clinic_data_is_isolated_between_clinics(client: AsyncClient) -> None:
    clinic_a = await register(client, email="a@example.com", clinic_name="Clinic A")
    clinic_b = await register(client, email="b@example.com", clinic_name="Clinic B")

    # Owner A tries to read clinic B by sending B's id.
    sneaky = {**clinic_a, "X-Clinic-Id": clinic_b["X-Clinic-Id"]}
    assert (await client.get(f"{API}/clinics/current", headers=sneaky)).status_code == 403
    assert (await client.get(f"{API}/clinics/current/members", headers=sneaky)).status_code == 403

    own = await client.get(f"{API}/clinics/current", headers=clinic_a)
    assert own.status_code == 200 and own.json()["name"] == "Clinic A"


async def test_clinic_header_is_required(client: AsyncClient) -> None:
    headers = await register(client)
    no_clinic = {"Authorization": headers["Authorization"]}
    assert (await client.get(f"{API}/clinics/current", headers=no_clinic)).status_code == 422


async def test_owner_can_update_clinic_details(client: AsyncClient) -> None:
    owner = await register(client)
    r = await client.patch(
        f"{API}/clinics/current",
        json={"city": "Ludhiana", "pincode": "141001", "gstin": "03abcde1234f1z5"},
        headers=owner,
    )
    assert r.status_code == 200
    assert r.json()["gstin"] == "03ABCDE1234F1Z5"

    bad = await client.patch(f"{API}/clinics/current", json={"pincode": "12"}, headers=owner)
    assert bad.status_code == 422


async def test_invite_flow_and_role_permissions(client: AsyncClient, outbox: Outbox) -> None:
    owner = await register(client)

    # Lookup shows what the invite page needs, before accepting.
    await client.post(
        f"{API}/invitations", json={"email": "Doc@Example.com", "role": "doctor"}, headers=owner
    )
    assert "Sunrise Clinic" in outbox.messages[-1].subject
    lookup = await client.get(f"{API}/invitations/lookup", params={"token": outbox.last_token()})
    assert lookup.json()["email"] == "doc@example.com"
    assert lookup.json()["needs_name"] and lookup.json()["needs_password"]

    doctor = await invite_and_accept(client, outbox, owner, "doc@example.com", "doctor")

    members = (await client.get(f"{API}/clinics/current/members", headers=doctor)).json()
    assert {m["role"] for m in members} == {"owner", "doctor"}

    # Doctors can view, but not change clinic settings or invite people.
    assert (await client.get(f"{API}/clinics/current", headers=doctor)).status_code == 200
    patch = await client.patch(f"{API}/clinics/current", json={"city": "X"}, headers=doctor)
    invite = await client.post(
        f"{API}/invitations", json={"email": "x@example.com", "role": "doctor"}, headers=doctor
    )
    assert patch.status_code == invite.status_code == 403


async def test_invitation_link_single_use_and_revocable(
    client: AsyncClient, outbox: Outbox
) -> None:
    owner = await register(client)
    await invite_and_accept(client, outbox, owner, "rec@example.com", "receptionist")
    reuse = await client.post(
        f"{API}/invitations/accept",
        json={"token": outbox.last_token(), "profile": staff(), "password": "staff-pass-123"},
    )
    assert reuse.status_code == 404

    r = await client.post(
        f"{API}/invitations", json={"email": "later@example.com", "role": "doctor"}, headers=owner
    )
    pending = (await client.get(f"{API}/invitations", headers=owner)).json()
    assert [p["email"] for p in pending] == ["later@example.com"]

    await client.delete(f"{API}/invitations/{r.json()['id']}", headers=owner)
    lookup = await client.get(f"{API}/invitations/lookup", params={"token": outbox.last_token()})
    assert lookup.status_code == 404


async def test_existing_user_joins_second_clinic(client: AsyncClient, outbox: Outbox) -> None:
    await register(client, email="doc@example.com", clinic_name="Doc's Own Clinic")
    # Verify the doctor's email via a password reset (proves they own it).
    await client.post(f"{API}/auth/password/forgot", json={"email": "doc@example.com"})
    await client.post(
        f"{API}/auth/password/reset",
        json={"token": outbox.last_token(), "new_password": "doc-password-1"},
    )

    owner = await register(client, email="owner2@example.com", clinic_name="Big Hospital")
    await client.post(
        f"{API}/invitations", json={"email": "doc@example.com", "role": "doctor"}, headers=owner
    )
    lookup = await client.get(f"{API}/invitations/lookup", params={"token": outbox.last_token()})
    assert lookup.json()["needs_name"] is False and lookup.json()["needs_password"] is False

    accepted = await client.post(f"{API}/invitations/accept", json={"token": outbox.last_token()})
    me = (await client.get(f"{API}/auth/me", headers=bearer(accepted))).json()
    assert sorted(m["clinic_name"] for m in me["memberships"]) == [
        "Big Hospital",
        "Doc's Own Clinic",
    ]


async def test_clinic_always_keeps_an_owner(client: AsyncClient, outbox: Outbox) -> None:
    owner = await register(client)
    members = (await client.get(f"{API}/clinics/current/members", headers=owner)).json()
    me_member = members[0]["id"]

    demote = await client.patch(
        f"{API}/clinics/current/members/{me_member}", json={"role": "doctor"}, headers=owner
    )
    assert demote.status_code == 400

    # Deactivating a doctor removes their access.
    doctor = await invite_and_accept(client, outbox, owner, "doc@example.com", "doctor")
    members = (await client.get(f"{API}/clinics/current/members", headers=owner)).json()
    doc_member = next(m["id"] for m in members if m["role"] == "doctor")
    r = await client.patch(
        f"{API}/clinics/current/members/{doc_member}", json={"is_active": False}, headers=owner
    )
    assert r.status_code == 200
    assert (await client.get(f"{API}/clinics/current", headers=doctor)).status_code == 403
