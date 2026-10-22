"""Doctor working hours, slots, booking, walk-in tokens, status flow and double-booking."""

import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from tests.conftest import Outbox, PhoneOutbox, bearer, register

API = "/api/v1"
IST = ZoneInfo("Asia/Kolkata")

MORNING = {"start_time": "10:00", "end_time": "13:00", "slot_minutes": 15}


def next_weekday(weekday: int) -> date:
    """The next date (after today, in IST) that falls on `weekday` (0 = Monday)."""
    today = datetime.now(IST).date()
    days = (weekday - today.weekday()) % 7 or 7
    return today + timedelta(days=days)


def at(day: date, hhmm: str) -> str:
    hour, minute = map(int, hhmm.split(":"))
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST).isoformat()


async def setup_clinic(client: AsyncClient, **register_kwargs) -> tuple[dict, str, str]:
    """An owner who is a doctor (Dr.), with Monday mornings, and one patient."""
    owner = await register(client, **register_kwargs)
    me = (await client.get(f"{API}/auth/me", headers=owner)).json()
    doctor_id = me["user"]["id"]
    r = await client.put(
        f"{API}/doctors/{doctor_id}/schedule",
        json={"sessions": [{"weekday": 0, **MORNING}]},
        headers=owner,
    )
    assert r.status_code == 200, r.text
    patient = await client.post(
        f"{API}/patients",
        json={"full_name": "Kavya Sethi", "phone": "+919810055555", "messaging_consent": True},
        headers=owner,
    )
    return owner, doctor_id, patient.json()["id"]


async def book(client, headers, patient_id, doctor_id, start_at, **extra):
    return await client.post(
        f"{API}/appointments",
        json={"patient_id": patient_id, "doctor_id": doctor_id, "start_at": start_at, **extra},
        headers=headers,
    )


async def test_schedule_and_doctor_list(client: AsyncClient) -> None:
    owner, doctor_id, _ = await setup_clinic(client)
    doctors = (await client.get(f"{API}/doctors", headers=owner)).json()
    assert len(doctors) == 1 and doctors[0]["user_id"] == doctor_id
    assert doctors[0]["sessions"] == [
        {"weekday": 0, "start_time": "10:00:00", "end_time": "13:00:00", "slot_minutes": 15}
    ]

    overlapping = await client.put(
        f"{API}/doctors/{doctor_id}/schedule",
        json={
            "sessions": [
                {"weekday": 1, **MORNING},
                {"weekday": 1, "start_time": "12:00", "end_time": "14:00", "slot_minutes": 15},
            ]
        },
        headers=owner,
    )
    backwards = await client.put(
        f"{API}/doctors/{doctor_id}/schedule",
        json={"sessions": [{"weekday": 1, "start_time": "13:00", "end_time": "10:00"}]},
        headers=owner,
    )
    assert overlapping.status_code == backwards.status_code == 422


async def test_only_owner_or_the_doctor_edits_hours(client: AsyncClient, outbox: Outbox) -> None:
    owner, doctor_id, _ = await setup_clinic(client)
    from tests.test_clinics import invite_and_accept  # noqa: PLC0415

    receptionist = await invite_and_accept(client, outbox, owner, "rec@example.com", "receptionist")
    r = await client.put(
        f"{API}/doctors/{doctor_id}/schedule", json={"sessions": []}, headers=receptionist
    )
    assert r.status_code == 403

    # Receptionists aren't doctors, so they can't be given hours either.
    rec_id = (await client.get(f"{API}/auth/me", headers=receptionist)).json()["user"]["id"]
    r = await client.put(f"{API}/doctors/{rec_id}/schedule", json={"sessions": []}, headers=owner)
    assert r.status_code == 404


async def test_slots_follow_hours_and_bookings(client: AsyncClient) -> None:
    owner, doctor_id, patient_id = await setup_clinic(client)
    monday = next_weekday(0)
    slots = (
        await client.get(
            f"{API}/appointments/slots",
            params={"doctor_id": doctor_id, "date": monday.isoformat()},
            headers=owner,
        )
    ).json()
    assert len(slots) == 12 and all(s["available"] for s in slots)  # 10:00–13:00 in 15 min

    await book(client, owner, patient_id, doctor_id, at(monday, "10:15"))
    slots = (
        await client.get(
            f"{API}/appointments/slots",
            params={"doctor_id": doctor_id, "date": monday.isoformat()},
            headers=owner,
        )
    ).json()
    taken = [s for s in slots if not s["available"]]
    assert len(taken) == 1
    assert datetime.fromisoformat(taken[0]["start_at"]).astimezone(IST).strftime("%H:%M") == "10:15"

    tuesday = (
        await client.get(
            f"{API}/appointments/slots",
            params={"doctor_id": doctor_id, "date": (monday + timedelta(days=1)).isoformat()},
            headers=owner,
        )
    ).json()
    assert tuesday == []  # not working on Tuesdays


async def test_booking_rules(client: AsyncClient, whatsapp_outbox: PhoneOutbox) -> None:
    owner, doctor_id, patient_id = await setup_clinic(client)
    monday = next_weekday(0)

    ok = await book(client, owner, patient_id, doctor_id, at(monday, "10:00"), reason="Fever")
    assert ok.status_code == 201, ok.text
    appt = ok.json()
    assert appt["status"] == "booked" and appt["kind"] == "scheduled"
    assert appt["visit_date"] == monday.isoformat() and appt["token_number"] is None
    assert appt["patient_name"] == "Kavya Sethi" and appt["reason"] == "Fever"
    end = datetime.fromisoformat(appt["end_at"]) - datetime.fromisoformat(appt["start_at"])
    assert end == timedelta(minutes=15)

    # WhatsApp confirmation (the patient consented).
    sent = whatsapp_outbox.messages[-1]
    assert sent.to == "+919810055555" and "confirmed for" in sent.render()

    taken = await book(client, owner, patient_id, doctor_id, at(monday, "10:00"))
    overlap = await book(client, owner, patient_id, doctor_id, at(monday, "10:05"))
    closed = await book(client, owner, patient_id, doctor_id, at(monday, "15:00"))
    last = await book(client, owner, patient_id, doctor_id, at(monday, "12:50"))  # ends 13:05
    past = await book(client, owner, patient_id, doctor_id, at(monday - timedelta(days=7), "10:00"))
    assert taken.status_code == overlap.status_code == 409
    assert "already has an appointment at 10:00 AM" in taken.json()["detail"]
    assert closed.status_code == last.status_code == past.status_code == 400
    no_time = await client.post(
        f"{API}/appointments",
        json={"patient_id": patient_id, "doctor_id": doctor_id},
        headers=owner,
    )
    assert no_time.status_code == 422


async def test_no_confirmation_without_consent(
    client: AsyncClient, whatsapp_outbox: PhoneOutbox
) -> None:
    owner, doctor_id, _ = await setup_clinic(client)
    patient = await client.post(
        f"{API}/patients",
        json={"full_name": "No Consent", "phone": "+919000012345"},
        headers=owner,
    )
    r = await book(client, owner, patient.json()["id"], doctor_id, at(next_weekday(0), "11:00"))
    assert r.status_code == 201 and whatsapp_outbox.messages == []


async def test_simultaneous_bookings_of_one_slot(client: AsyncClient) -> None:
    """Two receptionists click "Book" for the same slot at the same moment."""
    owner, doctor_id, patient_id = await setup_clinic(client)
    start = at(next_weekday(0), "11:30")
    results = await asyncio.gather(
        *[book(client, owner, patient_id, doctor_id, start) for _ in range(4)]
    )
    codes = sorted(r.status_code for r in results)
    assert codes == [201, 409, 409, 409]


async def test_walk_ins_get_tokens_and_move_through_the_day(client: AsyncClient) -> None:
    owner, doctor_id, patient_id = await setup_clinic(client)
    first = await client.post(
        f"{API}/appointments",
        json={"patient_id": patient_id, "doctor_id": doctor_id, "kind": "walk_in"},
        headers=owner,
    )
    second = await client.post(
        f"{API}/appointments",
        json={"patient_id": patient_id, "doctor_id": doctor_id, "kind": "walk_in"},
        headers=owner,
    )
    assert first.status_code == 201, first.text
    assert (first.json()["token_number"], second.json()["token_number"]) == (1, 2)
    assert first.json()["status"] == "arrived" and first.json()["arrived_at"]

    url = f"{API}/appointments/{first.json()['id']}/status"
    skip = await client.post(url, json={"status": "completed"}, headers=owner)
    assert skip.status_code == 400 and "can't be marked completed" in skip.json()["detail"]
    start = await client.post(url, json={"status": "in_consultation"}, headers=owner)
    done = await client.post(url, json={"status": "completed"}, headers=owner)
    assert start.json()["started_at"] and done.json()["status"] == "completed"
    again = await client.post(url, json={"status": "cancelled"}, headers=owner)
    assert again.status_code == 400


async def test_check_in_only_on_the_day(client: AsyncClient) -> None:
    owner, doctor_id, patient_id = await setup_clinic(client)
    future = (await book(client, owner, patient_id, doctor_id, at(next_weekday(0), "10:00"))).json()
    r = await client.post(
        f"{API}/appointments/{future['id']}/status", json={"status": "arrived"}, headers=owner
    )
    assert r.status_code == 400 and "today" in r.json()["detail"]


async def test_scheduled_check_in_today_gets_next_token(client: AsyncClient) -> None:
    owner = await register(client)
    me = (await client.get(f"{API}/auth/me", headers=owner)).json()
    doctor_id = me["user"]["id"]
    now = datetime.now(IST)
    slot = now.replace(second=0, microsecond=0) + timedelta(minutes=5 - now.minute % 5)
    if slot.date() != now.date() or slot.hour == 23 and slot.minute > 40:
        pytest.skip("Too close to midnight in IST to book a slot today")
    await client.put(
        f"{API}/doctors/{doctor_id}/schedule",
        json={
            "sessions": [
                {
                    "weekday": now.weekday(),
                    "start_time": "00:00",
                    "end_time": "23:55",
                    "slot_minutes": 5,
                }
            ]
        },
        headers=owner,
    )
    patient = (
        await client.post(
            f"{API}/patients",
            json={"full_name": "Today Patient", "phone": "+919000012345"},
            headers=owner,
        )
    ).json()
    walk_in = await client.post(
        f"{API}/appointments",
        json={"patient_id": patient["id"], "doctor_id": doctor_id, "kind": "walk_in"},
        headers=owner,
    )
    booked = await book(client, owner, patient["id"], doctor_id, slot.isoformat())
    assert booked.status_code == 201, booked.text
    arrived = await client.post(
        f"{API}/appointments/{booked.json()['id']}/status",
        json={"status": "arrived"},
        headers=owner,
    )
    assert arrived.status_code == 200
    assert (walk_in.json()["token_number"], arrived.json()["token_number"]) == (1, 2)


async def test_reschedule_and_cancel_frees_the_slot(client: AsyncClient) -> None:
    owner, doctor_id, patient_id = await setup_clinic(client)
    monday = next_weekday(0)
    a = (await book(client, owner, patient_id, doctor_id, at(monday, "10:00"))).json()
    b = (await book(client, owner, patient_id, doctor_id, at(monday, "10:30"))).json()

    clash = await client.patch(
        f"{API}/appointments/{a['id']}", json={"start_at": at(monday, "10:30")}, headers=owner
    )
    assert clash.status_code == 409
    moved = await client.patch(
        f"{API}/appointments/{a['id']}", json={"start_at": at(monday, "11:00")}, headers=owner
    )
    assert moved.status_code == 200
    moved_to = datetime.fromisoformat(moved.json()["start_at"]).astimezone(IST)
    assert moved_to.strftime("%H:%M") == "11:00"
    # Moving within its own slot range isn't a clash with itself.
    same = await client.patch(
        f"{API}/appointments/{a['id']}", json={"reason": "Follow-up"}, headers=owner
    )
    assert same.status_code == 200 and same.json()["reason"] == "Follow-up"

    await client.post(
        f"{API}/appointments/{b['id']}/status", json={"status": "cancelled"}, headers=owner
    )
    rebook = await book(client, owner, patient_id, doctor_id, at(monday, "10:30"))
    assert rebook.status_code == 201  # a cancelled booking no longer holds the time
    cant_move = await client.patch(
        f"{API}/appointments/{b['id']}", json={"start_at": at(monday, "12:00")}, headers=owner
    )
    assert cant_move.status_code == 400


async def test_listing_by_day_doctor_and_patient(client: AsyncClient) -> None:
    owner, doctor_id, patient_id = await setup_clinic(client)
    monday = next_weekday(0)
    await book(client, owner, patient_id, doctor_id, at(monday, "11:00"))
    await book(client, owner, patient_id, doctor_id, at(monday, "10:00"))
    await book(client, owner, patient_id, doctor_id, at(monday + timedelta(days=7), "10:00"))

    day = (
        await client.get(
            f"{API}/appointments", params={"start_date": monday.isoformat()}, headers=owner
        )
    ).json()
    times = [datetime.fromisoformat(a["start_at"]).astimezone(IST).strftime("%H:%M") for a in day]
    assert times == ["10:00", "11:00"]  # in time order
    week = await client.get(
        f"{API}/appointments",
        params={
            "start_date": monday.isoformat(),
            "end_date": (monday + timedelta(days=7)).isoformat(),
        },
        headers=owner,
    )
    assert len(week.json()) == 3
    history = await client.get(
        f"{API}/appointments", params={"patient_id": patient_id}, headers=owner
    )
    assert len(history.json()) == 3
    too_long = await client.get(
        f"{API}/appointments",
        params={
            "start_date": monday.isoformat(),
            "end_date": (monday + timedelta(days=40)).isoformat(),
        },
        headers=owner,
    )
    assert too_long.status_code == 400


async def test_appointments_are_private_to_each_clinic(client: AsyncClient) -> None:
    owner, doctor_id, patient_id = await setup_clinic(client, email="a@example.com")
    appt = (await book(client, owner, patient_id, doctor_id, at(next_weekday(0), "10:00"))).json()
    other = await register(client, email="b@example.com", clinic_name="Other Clinic")
    assert (
        await client.get(f"{API}/appointments", params={"patient_id": patient_id}, headers=other)
    ).json() == []
    r = await client.post(
        f"{API}/appointments/{appt['id']}/status", json={"status": "cancelled"}, headers=other
    )
    assert r.status_code == 404
    # Can't book clinic A's patient or doctor from clinic B.
    assert (
        await book(client, other, patient_id, doctor_id, at(next_weekday(0), "11:00"))
    ).status_code == 404


async def test_patient_app_shows_appointments(
    client: AsyncClient, whatsapp_outbox: PhoneOutbox
) -> None:
    owner, doctor_id, _ = await setup_clinic(client)
    patient = (
        await client.post(
            f"{API}/patients",
            json={
                "full_name": "Arjun Sethi",
                "phone": "+919000077777",
                "date_of_birth": "2019-03-02",
            },
            headers=owner,
        )
    ).json()
    await book(
        client, owner, patient["id"], doctor_id, at(next_weekday(0), "12:00"), reason="Vaccination"
    )

    await client.post(f"{API}/patient/auth/otp", json={"phone": "+919000077777"})
    login = await client.post(
        f"{API}/patient/auth/login",
        json={"phone": "+919000077777", "code": whatsapp_outbox.last_code()},
    )
    app_headers = bearer(login)
    profile = (await client.get(f"{API}/patient/me", headers=app_headers)).json()["profiles"][0]
    await client.post(
        f"{API}/patient/profiles/{profile['id']}/verify",
        json={"date_of_birth": "2019-03-02"},
        headers=app_headers,
    )
    details = (
        await client.get(f"{API}/patient/profiles/{profile['id']}", headers=app_headers)
    ).json()
    assert len(details["appointments"]) == 1
    card = details["appointments"][0]
    assert card["reason"] == "Vaccination" and card["status"] == "booked"
    assert card["doctor_name"].startswith("Dr. ")


async def test_reschedule_sends_the_new_time(
    client: AsyncClient, whatsapp_outbox: PhoneOutbox
) -> None:
    owner, doctor_id, patient_id = await setup_clinic(client)
    monday = next_weekday(0)
    appt = (await book(client, owner, patient_id, doctor_id, at(monday, "10:30"))).json()
    assert "10:30 AM" in whatsapp_outbox.messages[-1].render()
    await client.patch(
        f"{API}/appointments/{appt['id']}", json={"start_at": at(monday, "11:00")}, headers=owner
    )
    assert "11:00 AM" in whatsapp_outbox.messages[-1].render()
    sent = len(whatsapp_outbox.messages)
    await client.patch(
        f"{API}/appointments/{appt['id']}", json={"reason": "BP check"}, headers=owner
    )
    assert len(whatsapp_outbox.messages) == sent  # only time changes are announced
