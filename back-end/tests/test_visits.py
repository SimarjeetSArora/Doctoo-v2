"""Consultations and prescriptions: start, write, finish (lock + number), PDF, WhatsApp, app."""

from datetime import date, timedelta

from httpx import AsyncClient

from tests.conftest import Outbox, PhoneOutbox, bearer, register

API = "/api/v1"
YEAR = date.today().year

GOOD_VISIT = {
    "vitals": {
        "bp_systolic": 128,
        "bp_diastolic": 84,
        "pulse": 78,
        "temperature_f": 100.4,
        "spo2": 98,
    },
    "complaints": "Fever and sore throat for 2 days",
    "examination": "Throat congested",
    "diagnosis": "Acute pharyngitis",
    "advice": "Warm salt-water gargles. Plenty of fluids.",
    "follow_up_date": (date.today() + timedelta(days=5)).isoformat(),
    "items": [
        {
            "medicine": "Paracetamol 650 mg",
            "dose": "1-0-1",
            "timing": "After food",
            "duration": "5 days",
        },
        {
            "medicine": "Azithromycin 500 mg",
            "dose": "1-0-0",
            "timing": "Before food",
            "duration": "3 days",
            "instructions": "Complete the course",
        },
    ],
}


async def setup(client: AsyncClient, consent: bool = True, name: str = "Kavya Sethi") -> dict:
    """Owner (a Dr.), one patient who walked in. Returns ids and headers."""
    owner = await register(client)
    doctor_id = (await client.get(f"{API}/auth/me", headers=owner)).json()["user"]["id"]
    patient = (
        await client.post(
            f"{API}/patients",
            json={
                "full_name": name,
                "phone": "+919810055555",
                "date_of_birth": "1995-06-15",
                "messaging_consent": consent,
                "notes": "Allergic to sulfa drugs",
            },
            headers=owner,
        )
    ).json()
    walk_in = await client.post(
        f"{API}/appointments",
        json={"patient_id": patient["id"], "doctor_id": doctor_id, "kind": "walk_in"},
        headers=owner,
    )
    return {
        "owner": owner,
        "doctor_id": doctor_id,
        "patient": patient,
        "appointment": walk_in.json(),
    }


async def start(client: AsyncClient, ctx: dict, headers: dict | None = None):
    return await client.post(
        f"{API}/appointments/{ctx['appointment']['id']}/consultation",
        headers=headers or ctx["owner"],
    )


async def finished_visit(client: AsyncClient, ctx: dict) -> dict:
    visit = (await start(client, ctx)).json()
    await client.patch(f"{API}/visits/{visit['id']}", json=GOOD_VISIT, headers=ctx["owner"])
    return (await client.post(f"{API}/visits/{visit['id']}/complete", headers=ctx["owner"])).json()


async def test_consultation_flow(client: AsyncClient) -> None:
    ctx = await setup(client)
    started = await start(client, ctx)
    assert started.status_code == 200, started.text
    visit = started.json()
    assert visit["status"] == "in_progress" and visit["can_edit"]
    assert visit["patient"]["notes"] == "Allergic to sulfa drugs"  # shown to the doctor
    again = await start(client, ctx)
    assert again.json()["id"] == visit["id"]  # reopening returns the same consultation

    appt = (await client.get(f"{API}/appointments", headers=ctx["owner"])).json()[0]
    assert appt["status"] == "in_consultation"

    saved = await client.patch(f"{API}/visits/{visit['id']}", json=GOOD_VISIT, headers=ctx["owner"])
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["vitals"]["bp_systolic"] == 128 and body["vitals"]["weight_kg"] is None
    assert [i["medicine"] for i in body["items"]] == ["Paracetamol 650 mg", "Azithromycin 500 mg"]
    assert body["prescription_number"] is None

    done = await client.post(f"{API}/visits/{visit['id']}/complete", headers=ctx["owner"])
    assert done.status_code == 200
    assert done.json()["status"] == "completed" and not done.json()["can_edit"]
    assert done.json()["prescription_number"] == f"RX-{YEAR}-00001"
    appt = (await client.get(f"{API}/appointments", headers=ctx["owner"])).json()[0]
    assert appt["status"] == "completed"

    # Finished records are locked.
    locked = await client.patch(
        f"{API}/visits/{visit['id']}", json={"advice": "x"}, headers=ctx["owner"]
    )
    assert locked.status_code == 409
    twice = await client.post(f"{API}/visits/{visit['id']}/complete", headers=ctx["owner"])
    assert twice.status_code == 409

    history = (
        await client.get(
            f"{API}/visits", params={"patient_id": ctx["patient"]["id"]}, headers=ctx["owner"]
        )
    ).json()
    assert history[0]["diagnosis"] == "Acute pharyngitis" and len(history[0]["medicines"]) == 2


async def test_prescription_numbers_increase(client: AsyncClient) -> None:
    ctx = await setup(client)
    first = await finished_visit(client, ctx)
    walk_in = await client.post(
        f"{API}/appointments",
        json={"patient_id": ctx["patient"]["id"], "doctor_id": ctx["doctor_id"], "kind": "walk_in"},
        headers=ctx["owner"],
    )
    second = await finished_visit(client, {**ctx, "appointment": walk_in.json()})
    assert (first["prescription_number"], second["prescription_number"]) == (
        f"RX-{YEAR}-00001",
        f"RX-{YEAR}-00002",
    )


async def test_rules_for_starting_and_finishing(client: AsyncClient) -> None:
    ctx = await setup(client)
    # Can't finish an empty consultation.
    visit = (await start(client, ctx)).json()
    empty = await client.post(f"{API}/visits/{visit['id']}/complete", headers=ctx["owner"])
    assert empty.status_code == 400

    # Can't start before the patient is checked in.
    from tests.test_appointments import at, next_weekday  # noqa: PLC0415

    await client.put(
        f"{API}/doctors/{ctx['doctor_id']}/schedule",
        json={"sessions": [{"weekday": 0, "start_time": "10:00", "end_time": "13:00"}]},
        headers=ctx["owner"],
    )
    booked = await client.post(
        f"{API}/appointments",
        json={
            "patient_id": ctx["patient"]["id"],
            "doctor_id": ctx["doctor_id"],
            "start_at": at(next_weekday(0), "10:00"),
        },
        headers=ctx["owner"],
    )
    early = await client.post(
        f"{API}/appointments/{booked.json()['id']}/consultation", headers=ctx["owner"]
    )
    assert early.status_code == 400 and "Check the patient in" in early.json()["detail"]


async def test_vitals_and_items_are_validated(client: AsyncClient) -> None:
    ctx = await setup(client)
    visit = (await start(client, ctx)).json()
    url = f"{API}/visits/{visit['id']}"
    for bad in (
        {"vitals": {"spo2": 140}},
        {"vitals": {"temperature_f": 1000}},
        {"items": [{"medicine": "", "dose": "1-0-1"}]},
        {"items": [{"medicine": "Paracetamol", "dose": ""}]},
    ):
        assert (await client.patch(url, json=bad, headers=ctx["owner"])).status_code == 422, bad


async def test_only_the_doctor_or_owner_writes(client: AsyncClient, outbox: Outbox) -> None:
    ctx = await setup(client)
    from tests.test_clinics import invite_and_accept  # noqa: PLC0415

    receptionist = await invite_and_accept(
        client, outbox, ctx["owner"], "rec@example.com", "receptionist"
    )
    other_doctor = await invite_and_accept(
        client, outbox, ctx["owner"], "doc2@example.com", "doctor"
    )
    assert (await start(client, ctx, receptionist)).status_code == 403
    assert (await start(client, ctx, other_doctor)).status_code == 403

    visit = (await start(client, ctx)).json()
    url = f"{API}/visits/{visit['id']}"
    viewed = await client.get(url, headers=receptionist)
    assert viewed.status_code == 200 and viewed.json()["can_edit"] is False  # can view, not edit
    assert (await client.patch(url, json={"advice": "x"}, headers=receptionist)).status_code == 403
    assert (await client.patch(url, json={"advice": "x"}, headers=other_doctor)).status_code == 403


async def test_pdf_and_medicine_suggestions(client: AsyncClient) -> None:
    ctx = await setup(client, name="अनीता शर्मा")  # Hindi name must not break the PDF
    visit = await finished_visit(client, ctx)
    pdf = await client.get(f"{API}/visits/{visit['id']}/prescription.pdf", headers=ctx["owner"])
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF") and len(pdf.content) > 2000
    assert f"RX-{YEAR}-00001" in pdf.headers["content-disposition"]

    suggestions = await client.get(f"{API}/medicines", params={"q": "para"}, headers=ctx["owner"])
    assert [m["name"] for m in suggestions.json()] == ["Paracetamol 650 mg"]
    assert suggestions.json()[0]["times_used"] == 1


async def test_share_on_whatsapp(client: AsyncClient, whatsapp_outbox: PhoneOutbox) -> None:
    ctx = await setup(client)
    visit = (await start(client, ctx)).json()
    early = await client.post(f"{API}/visits/{visit['id']}/share", headers=ctx["owner"])
    assert early.status_code == 400  # not finished yet

    visit = await finished_visit(client, ctx)
    sent_before = len(whatsapp_outbox.messages)
    r = await client.post(f"{API}/visits/{visit['id']}/share", headers=ctx["owner"])
    assert r.status_code == 200 and r.json()["sent_to"] == "+919810055555"
    message = whatsapp_outbox.messages[-1]
    assert len(whatsapp_outbox.messages) == sent_before + 1
    assert "here is your prescription" in message.render()
    assert message.document_name.startswith(f"RX-{YEAR}-00001")

    # The link in the message opens the PDF without logging in…
    path = message.document_url.split("/api/v1", 1)[1]
    opened = await client.get(f"{API}{path}")
    assert opened.status_code == 200 and opened.content.startswith(b"%PDF")
    # …but a made-up link doesn't.
    assert (await client.get(f"{API}/public/prescriptions/not-a-real-token")).status_code == 404


async def test_no_sharing_without_consent(client: AsyncClient) -> None:
    ctx = await setup(client, consent=False)
    visit = await finished_visit(client, ctx)
    r = await client.post(f"{API}/visits/{visit['id']}/share", headers=ctx["owner"])
    assert r.status_code == 400 and "consent" in r.json()["detail"]


async def test_visits_are_private_to_each_clinic(client: AsyncClient) -> None:
    ctx = await setup(client)
    visit = await finished_visit(client, ctx)
    other = await register(client, email="other@example.com", clinic_name="Other Clinic")
    assert (await client.get(f"{API}/visits/{visit['id']}", headers=other)).status_code == 404
    assert (
        await client.get(f"{API}/visits/{visit['id']}/prescription.pdf", headers=other)
    ).status_code == 404


async def test_patient_app_prescriptions(client: AsyncClient, whatsapp_outbox: PhoneOutbox) -> None:
    ctx = await setup(client)
    visit = await finished_visit(client, ctx)
    await client.post(f"{API}/patient/auth/otp", json={"phone": "+919810055555"})
    login = await client.post(
        f"{API}/patient/auth/login",
        json={"phone": "+919810055555", "code": whatsapp_outbox.last_code()},
    )
    app = bearer(login)
    profile = (await client.get(f"{API}/patient/me", headers=app)).json()["profiles"][0]
    pdf_url = f"{API}/patient/profiles/{profile['id']}/prescriptions/{visit['id']}.pdf"
    assert (await client.get(pdf_url, headers=app)).status_code == 403  # DOB not confirmed yet

    await client.post(
        f"{API}/patient/profiles/{profile['id']}/verify",
        json={"date_of_birth": "1995-06-15"},
        headers=app,
    )
    details = (await client.get(f"{API}/patient/profiles/{profile['id']}", headers=app)).json()
    card = details["prescriptions"][0]
    assert card["number"] == f"RX-{YEAR}-00001" and card["diagnosis"] == "Acute pharyngitis"
    assert card["medicines"] == ["Paracetamol 650 mg", "Azithromycin 500 mg"]
    pdf = await client.get(pdf_url, headers=app)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert "attachment" in pdf.headers["content-disposition"]
