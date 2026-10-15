"""The patient app: login by WhatsApp code, family profiles, date-of-birth check, overview."""

from httpx import AsyncClient

from tests.conftest import PhoneOutbox, bearer, register

API = "/api/v1"
PHONE = "+919876543210"


async def add_patient(client: AsyncClient, clinic: dict, **fields) -> dict:
    body = {"full_name": "Anita Sharma", "phone": PHONE, "date_of_birth": "1990-04-12", **fields}
    r = await client.post(f"{API}/patients", json=body, headers=clinic)
    assert r.status_code == 201, r.text
    return r.json()


async def patient_login(client: AsyncClient, whatsapp_outbox: PhoneOutbox, phone: str = PHONE):
    sent = await client.post(f"{API}/patient/auth/otp", json={"phone": phone})
    assert sent.status_code == 200, sent.text
    r = await client.post(
        f"{API}/patient/auth/login", json={"phone": phone, "code": whatsapp_outbox.last_code()}
    )
    assert r.status_code == 200, r.text
    return bearer(r)


async def test_code_only_sent_to_registered_numbers(
    client: AsyncClient, whatsapp_outbox: PhoneOutbox
) -> None:
    clinic = await register(client)
    await add_patient(client, clinic)

    unknown = await client.post(f"{API}/patient/auth/otp", json={"phone": "+919000000001"})
    assert unknown.status_code == 200 and whatsapp_outbox.messages == []
    known = await client.post(f"{API}/patient/auth/otp", json={"phone": PHONE})
    assert known.json()["detail"] == unknown.json()["detail"]  # same reply either way
    assert whatsapp_outbox.messages[-1].to == PHONE


async def test_family_profiles_and_dob_check(
    client: AsyncClient, whatsapp_outbox: PhoneOutbox
) -> None:
    clinic_a = await register(client, email="a@example.com", clinic_name="Sunrise Clinic")
    clinic_b = await register(client, email="b@example.com", clinic_name="City Hospital")
    await add_patient(client, clinic_a)  # Anita at clinic A
    await add_patient(client, clinic_b, full_name="anita  sharma")  # same person at clinic B
    await add_patient(client, clinic_a, full_name="Aarav Sharma", date_of_birth="2018-09-01")
    await add_patient(client, clinic_a, full_name="Dadi Sharma", date_of_birth="")  # no DOB

    patient = await patient_login(client, whatsapp_outbox)
    me = (await client.get(f"{API}/patient/me", headers=patient)).json()
    assert me["phone"] == PHONE
    by_name = {p["name"]: p for p in me["profiles"]}
    assert set(by_name) == {"Anita S.", "Aarav S.", "Dadi S."}  # masked until confirmed
    anita = by_name["Anita S."]
    assert anita["clinic_count"] == 2 and not anita["verified"] and anita["can_verify"]
    assert by_name["Dadi S."]["can_verify"] is False

    # Details are hidden until the date of birth is confirmed.
    locked = await client.get(f"{API}/patient/profiles/{anita['id']}", headers=patient)
    assert locked.status_code == 403
    wrong = await client.post(
        f"{API}/patient/profiles/{anita['id']}/verify",
        json={"date_of_birth": "1991-01-01"},
        headers=patient,
    )
    assert wrong.status_code == 400 and "4 attempts left" in wrong.json()["detail"]
    ok = await client.post(
        f"{API}/patient/profiles/{anita['id']}/verify",
        json={"date_of_birth": "1990-04-12"},
        headers=patient,
    )
    assert ok.status_code == 204

    details = (await client.get(f"{API}/patient/profiles/{anita['id']}", headers=patient)).json()
    assert details["full_name"] == "Anita Sharma" and details["age"] >= 36
    assert sorted(c["name"] for c in details["clinics"]) == ["City Hospital", "Sunrise Clinic"]
    # Clinic owners registered as "Dr." count as doctors.
    assert sorted(d["clinic_name"] for d in details["doctors"]) == [
        "City Hospital",
        "Sunrise Clinic",
    ]
    assert details["prescriptions"] == [] and details["reports"] == []

    me = (await client.get(f"{API}/patient/me", headers=patient)).json()
    assert {p["name"] for p in me["profiles"]} == {"Anita Sharma", "Aarav S.", "Dadi S."}

    no_dob = await client.post(
        f"{API}/patient/profiles/{by_name['Dadi S.']['id']}/verify",
        json={"date_of_birth": "1950-01-01"},
        headers=patient,
    )
    assert no_dob.status_code == 400 and "hasn't recorded" in no_dob.json()["detail"]


async def test_dob_guessing_is_locked(client: AsyncClient, whatsapp_outbox: PhoneOutbox) -> None:
    clinic = await register(client)
    await add_patient(client, clinic)
    patient = await patient_login(client, whatsapp_outbox)
    profile = (await client.get(f"{API}/patient/me", headers=patient)).json()["profiles"][0]
    url = f"{API}/patient/profiles/{profile['id']}/verify"
    for _ in range(4):
        assert (
            await client.post(url, json={"date_of_birth": "2000-01-01"}, headers=patient)
        ).status_code == 400
    fifth = await client.post(url, json={"date_of_birth": "2000-01-01"}, headers=patient)
    assert fifth.status_code == 429
    right_but_locked = await client.post(url, json={"date_of_birth": "1990-04-12"}, headers=patient)
    assert right_but_locked.status_code == 429


async def test_patients_cannot_see_other_numbers(
    client: AsyncClient, whatsapp_outbox: PhoneOutbox
) -> None:
    clinic = await register(client)
    other = await add_patient(client, clinic, full_name="Someone Else", phone="+919000012345")
    await add_patient(client, clinic)
    patient = await patient_login(client, whatsapp_outbox)
    r = await client.get(f"{API}/patient/profiles/{other['id']}", headers=patient)
    assert r.status_code == 404


async def test_staff_and_patient_tokens_dont_mix(
    client: AsyncClient, whatsapp_outbox: PhoneOutbox
) -> None:
    clinic = await register(client)
    await add_patient(client, clinic)
    patient = await patient_login(client, whatsapp_outbox)

    assert (await client.get(f"{API}/auth/me", headers=patient)).status_code == 401
    staff_only = {"Authorization": clinic["Authorization"]}
    assert (await client.get(f"{API}/patient/me", headers=staff_only)).status_code == 401


async def test_patient_refresh_and_logout(
    client: AsyncClient, whatsapp_outbox: PhoneOutbox
) -> None:
    clinic = await register(client)
    await add_patient(client, clinic)
    await patient_login(client, whatsapp_outbox)
    refreshed = await client.post(f"{API}/patient/auth/refresh")
    assert refreshed.status_code == 200
    assert (await client.get(f"{API}/patient/me", headers=bearer(refreshed))).status_code == 200
    assert (await client.post(f"{API}/patient/auth/logout")).status_code == 204
    assert (await client.post(f"{API}/patient/auth/refresh")).status_code == 401


async def test_archived_patients_disappear_from_the_app(
    client: AsyncClient, whatsapp_outbox: PhoneOutbox
) -> None:
    clinic = await register(client)
    record = await add_patient(client, clinic)
    await add_patient(client, clinic, full_name="Aarav Sharma")
    patient = await patient_login(client, whatsapp_outbox)
    await client.delete(f"{API}/patients/{record['id']}", headers=clinic)
    me = (await client.get(f"{API}/patient/me", headers=patient)).json()
    assert [p["name"] for p in me["profiles"]] == ["Aarav S."]
