"""Clinic side: registering, searching, editing and archiving patients."""

from httpx import AsyncClient

from tests.conftest import Outbox, bearer, register

API = "/api/v1"

ANITA = {
    "full_name": "Anita Sharma",
    "phone": "+91 98765 43210",
    "date_of_birth": "1990-04-12",
    "gender": "female",
    "blood_group": "B+",
    "abha_number": "12345678901234",
    "notes": "Allergic to penicillin",
    "messaging_consent": True,
}


async def add(client: AsyncClient, headers: dict, **fields):
    return await client.post(f"{API}/patients", json={**ANITA, **fields}, headers=headers)


async def test_register_and_view_patient(client: AsyncClient) -> None:
    owner = await register(client)
    r = await add(client, owner)
    assert r.status_code == 201, r.text
    patient = r.json()
    assert patient["phone"] == "+919876543210"
    assert patient["abha_number"] == "12-3456-7890-1234"
    assert patient["age"] >= 36
    assert patient["messaging_consent"] is True and patient["messaging_consent_at"]

    got = await client.get(f"{API}/patients/{patient['id']}", headers=owner)
    assert got.json()["full_name"] == "Anita Sharma"


async def test_required_and_invalid_fields(client: AsyncClient) -> None:
    owner = await register(client)
    bad = [
        {"full_name": ""},
        {"phone": "12345"},
        {"date_of_birth": "2999-01-01"},
        {"blood_group": "C+"},
        {"abha_number": "123"},
        {"email": "not-an-email"},
    ]
    for fields in bad:
        r = await add(client, owner, **fields)
        assert r.status_code == 422, fields
    # Optional fields may be left blank.
    ok = await add(client, owner, email="", date_of_birth="", blood_group="", abha_number="")
    assert ok.status_code == 201 and ok.json()["email"] is None


async def test_search_by_name_or_phone(client: AsyncClient) -> None:
    owner = await register(client)
    await add(client, owner)
    await add(client, owner, full_name="Rohan Sharma", phone="+919000012345")
    await add(client, owner, full_name="Meera Kaur", phone="+919811122333")

    def names(r):
        return sorted(p["full_name"] for p in r.json()["items"])

    by_name = await client.get(f"{API}/patients", params={"q": "sharma"}, headers=owner)
    assert names(by_name) == ["Anita Sharma", "Rohan Sharma"] and by_name.json()["total"] == 2
    by_phone = await client.get(f"{API}/patients", params={"q": "98111"}, headers=owner)
    assert names(by_phone) == ["Meera Kaur"]
    everyone = await client.get(f"{API}/patients", headers=owner)
    assert everyone.json()["total"] == 3
    page = await client.get(f"{API}/patients", params={"limit": 2}, headers=owner)
    assert len(page.json()["items"]) == 2 and page.json()["total"] == 3
    tricky = await client.get(f"{API}/patients", params={"q": "%"}, headers=owner)
    assert tricky.json()["total"] == 0  # wildcards are treated as plain text


async def test_patients_are_private_to_each_clinic(client: AsyncClient) -> None:
    clinic_a = await register(client, email="a@example.com", clinic_name="Clinic A")
    clinic_b = await register(client, email="b@example.com", clinic_name="Clinic B")
    patient = (await add(client, clinic_a)).json()

    assert (await client.get(f"{API}/patients", headers=clinic_b)).json()["total"] == 0
    peek = await client.get(f"{API}/patients/{patient['id']}", headers=clinic_b)
    edit = await client.patch(
        f"{API}/patients/{patient['id']}", json={"full_name": "X Y"}, headers=clinic_b
    )
    assert peek.status_code == edit.status_code == 404


async def test_edit_patient_and_consent(client: AsyncClient) -> None:
    owner = await register(client)
    patient = (await add(client, owner)).json()
    r = await client.patch(
        f"{API}/patients/{patient['id']}",
        json={"notes": "No known allergies", "messaging_consent": False},
        headers=owner,
    )
    assert r.status_code == 200
    assert r.json()["notes"] == "No known allergies"
    assert r.json()["messaging_consent"] is False and r.json()["messaging_consent_at"] is None
    assert r.json()["full_name"] == "Anita Sharma"  # untouched fields stay

    cleared = await client.patch(
        f"{API}/patients/{patient['id']}", json={"full_name": None}, headers=owner
    )
    assert cleared.status_code == 422


async def test_archive_rules(client: AsyncClient, outbox: Outbox) -> None:
    owner = await register(client)
    patient = (await add(client, owner)).json()

    # Receptionists can register and edit, but not archive.
    await client.post(
        f"{API}/invitations",
        json={"email": "rec@example.com", "role": "receptionist"},
        headers=owner,
    )
    from tests.test_clinics import staff  # noqa: PLC0415

    accepted = await client.post(
        f"{API}/invitations/accept",
        json={"token": outbox.last_token(), "profile": staff(), "password": "staff-pass-123"},
    )
    receptionist = {**bearer(accepted), "X-Clinic-Id": owner["X-Clinic-Id"]}
    assert (await add(client, receptionist, full_name="Walk In")).status_code == 201
    denied = await client.delete(f"{API}/patients/{patient['id']}", headers=receptionist)
    assert denied.status_code == 403

    assert (
        await client.delete(f"{API}/patients/{patient['id']}", headers=owner)
    ).status_code == 204
    assert (await client.get(f"{API}/patients/{patient['id']}", headers=owner)).status_code == 404
    names = [
        p["full_name"] for p in (await client.get(f"{API}/patients", headers=owner)).json()["items"]
    ]
    assert names == ["Walk In"]


async def test_blank_optional_fields_sent_as_null(client: AsyncClient) -> None:
    """What the form sends when optional fields are left empty."""
    owner = await register(client)
    r = await client.post(
        f"{API}/patients",
        json={
            "full_name": "Kavya Sethi",
            "phone": "+919810055555",
            "email": None,
            "date_of_birth": None,
            "gender": None,
            "blood_group": None,
            "address": None,
            "abha_number": None,
            "notes": None,
            "messaging_consent": False,
        },
        headers=owner,
    )
    assert r.status_code == 201, r.text
    patch = await client.patch(
        f"{API}/patients/{r.json()['id']}", json={"address": None, "notes": None}, headers=owner
    )
    assert patch.status_code == 200
    too_long = await client.patch(
        f"{API}/patients/{r.json()['id']}", json={"address": "x" * 501}, headers=owner
    )
    assert too_long.status_code == 422
