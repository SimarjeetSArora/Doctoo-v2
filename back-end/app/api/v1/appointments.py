import uuid
from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import ClinicContext, ClinicCtx
from app.core.database import DbSession
from app.models import (
    Appointment,
    AppointmentKind,
    AppointmentStatus,
    Clinic,
    ClinicMember,
    DoctorSession,
    Patient,
    Role,
    User,
)
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentOut,
    AppointmentUpdate,
    DoctorOut,
    ScheduleUpdate,
    SessionOut,
    SlotOut,
    StatusChange,
)
from app.services.auth import utcnow
from app.services.scheduling import (
    DEFAULT_WALK_IN_MINUTES,
    build_slots,
    busy_times,
    clinic_doctors,
    clinic_zone,
    day_bounds,
    doctor_sessions,
    is_doctor,
    local_date,
    next_token,
    session_at,
)
from app.services.whatsapp import (
    WhatsAppMessage,
    WhatsAppSender,
    WhatsAppTemplate,
    deliver_whatsapp,
    get_whatsapp_sender,
)

router = APIRouter(tags=["appointments"])

# Booking a little in the past is allowed (the receptionist was slow to click), not more.
_PAST_GRACE = timedelta(minutes=5)

# Which status can follow which.
TRANSITIONS: dict[AppointmentStatus, set[AppointmentStatus]] = {
    AppointmentStatus.BOOKED: {
        AppointmentStatus.ARRIVED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    },
    AppointmentStatus.ARRIVED: {
        AppointmentStatus.IN_CONSULTATION,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    },
    AppointmentStatus.IN_CONSULTATION: {AppointmentStatus.COMPLETED},
}
STATUS_LABELS = {
    AppointmentStatus.BOOKED: "booked",
    AppointmentStatus.ARRIVED: "arrived",
    AppointmentStatus.IN_CONSULTATION: "in consultation",
    AppointmentStatus.COMPLETED: "completed",
    AppointmentStatus.NO_SHOW: "a no-show",
    AppointmentStatus.CANCELLED: "cancelled",
}


# ---------- Doctors and working hours ----------


async def _doctor(db: DbSession, ctx: ClinicContext, doctor_id: uuid.UUID) -> User:
    row = (
        await db.execute(
            select(ClinicMember, User)
            .join(User, User.id == ClinicMember.user_id)
            .where(
                ClinicMember.clinic_id == ctx.clinic_id,
                ClinicMember.user_id == doctor_id,
                ClinicMember.is_active,
                User.is_active,
            )
        )
    ).first()
    if row is None or not is_doctor(*row):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found in this clinic")
    return row[1]


def _sessions_out(sessions: list[DoctorSession]) -> list[SessionOut]:
    return [
        SessionOut(
            weekday=s.weekday,
            start_time=s.start_time,
            end_time=s.end_time,
            slot_minutes=s.slot_minutes,
        )
        for s in sessions
    ]


@router.get("/doctors")
async def list_doctors(ctx: ClinicCtx, db: DbSession) -> list[DoctorOut]:
    """Doctors at this clinic who can be booked, with their working hours."""
    doctors = await clinic_doctors(db, [ctx.clinic_id])
    return [
        DoctorOut(
            user_id=user.id,
            full_name=user.full_name,
            sessions=_sessions_out(await doctor_sessions(db, ctx.clinic_id, user.id)),
        )
        for _, user in doctors
    ]


@router.put("/doctors/{doctor_id}/schedule")
async def set_schedule(
    doctor_id: uuid.UUID, body: ScheduleUpdate, ctx: ClinicCtx, db: DbSession
) -> DoctorOut:
    """Replaces a doctor's working hours. Owners can edit anyone's; doctors only their own."""
    if ctx.role != Role.OWNER and ctx.user.id != doctor_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only change your own hours")
    doctor = await _doctor(db, ctx, doctor_id)
    await db.execute(
        delete(DoctorSession).where(
            DoctorSession.clinic_id == ctx.clinic_id, DoctorSession.doctor_id == doctor_id
        )
    )
    for session in body.sessions:
        db.add(DoctorSession(clinic_id=ctx.clinic_id, doctor_id=doctor_id, **session.model_dump()))
    await db.commit()
    sessions = await doctor_sessions(db, ctx.clinic_id, doctor_id)
    return DoctorOut(
        user_id=doctor.id, full_name=doctor.full_name, sessions=_sessions_out(sessions)
    )


# ---------- Slots ----------


@router.get("/appointments/slots")
async def available_slots(
    ctx: ClinicCtx, db: DbSession, doctor_id: uuid.UUID, day: Annotated[date, Query(alias="date")]
) -> list[SlotOut]:
    await _doctor(db, ctx, doctor_id)
    clinic = await db.get(Clinic, ctx.clinic_id)
    zone = clinic_zone(clinic)
    start, end = day_bounds(day, zone)
    slots = build_slots(
        await doctor_sessions(db, ctx.clinic_id, doctor_id),
        day,
        zone,
        await busy_times(db, doctor_id, start, end),
        now=utcnow(),
    )
    return [SlotOut(start_at=s.start_at, end_at=s.end_at, available=s.available) for s in slots]


# ---------- Appointments ----------


def _out(appointment: Appointment, patient: Patient, doctor: User) -> AppointmentOut:
    return AppointmentOut(
        id=appointment.id,
        kind=appointment.kind,
        status=appointment.status,
        start_at=appointment.start_at,
        end_at=appointment.end_at,
        visit_date=appointment.visit_date,
        token_number=appointment.token_number,
        reason=appointment.reason,
        notes=appointment.notes,
        patient_id=patient.id,
        patient_name=patient.full_name,
        patient_phone=patient.phone,
        doctor_id=doctor.id,
        doctor_name=doctor.full_name,
        arrived_at=appointment.arrived_at,
        started_at=appointment.started_at,
        completed_at=appointment.completed_at,
        cancelled_at=appointment.cancelled_at,
        created_at=appointment.created_at,
    )


@router.get("/appointments")
async def list_appointments(
    ctx: ClinicCtx,
    db: DbSession,
    start_date: date | None = None,
    end_date: date | None = None,
    doctor_id: uuid.UUID | None = None,
    patient_id: uuid.UUID | None = None,
) -> list[AppointmentOut]:
    """A day or date range (clinic's local dates), or one patient's history."""
    query = (
        select(Appointment, Patient, User)
        .join(Patient, Patient.id == Appointment.patient_id)
        .join(User, User.id == Appointment.doctor_id)
        .where(Appointment.clinic_id == ctx.clinic_id)
    )
    if patient_id:
        query = query.where(Appointment.patient_id == patient_id).order_by(
            Appointment.start_at.desc()
        )
        query = query.limit(100)
    else:
        clinic = await db.get(Clinic, ctx.clinic_id)
        first = start_date or local_date(utcnow(), clinic_zone(clinic))
        last = end_date or first
        if last < first or (last - first).days > 31:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose a range of up to 31 days")
        query = query.where(Appointment.visit_date.between(first, last)).order_by(
            Appointment.start_at
        )
    if doctor_id:
        query = query.where(Appointment.doctor_id == doctor_id)
    rows = await db.execute(query)
    return [_out(a, p, d) for a, p, d in rows.all()]


async def _patient(db: DbSession, ctx: ClinicContext, patient_id: uuid.UUID) -> Patient:
    patient = await db.scalar(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == ctx.clinic_id,
            Patient.deleted_at.is_(None),
        )
    )
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")
    return patient


async def _fit_slot(
    db: DbSession,
    ctx: ClinicContext,
    clinic: Clinic,
    doctor: User,
    start_at: datetime,
    ignore: uuid.UUID | None = None,
) -> datetime:
    """Checks the doctor works then and is free; returns the end time."""
    zone = clinic_zone(clinic)
    if start_at < utcnow() - _PAST_GRACE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That time has already passed")
    session = session_at(await doctor_sessions(db, ctx.clinic_id, doctor.id), start_at, zone)
    if session is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"{doctor.full_name} isn't working at that time"
        )
    end_at = start_at + timedelta(minutes=session.slot_minutes)
    if await busy_times(db, doctor.id, start_at, end_at, ignore=ignore):
        local = start_at.astimezone(zone).strftime("%I:%M %p").lstrip("0")
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"{doctor.full_name} already has an appointment at {local}"
        )
    return end_at


async def _commit_booking(db: DbSession) -> None:
    """Commits; a clash caught by the database's no-double-booking rule becomes a 409."""
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That slot was just taken. Please pick another time."
        ) from exc


def _confirmation(patient: Patient, doctor: User, clinic: Clinic, start_at: datetime):
    when = start_at.astimezone(clinic_zone(clinic)).strftime("%a, %d %b at %I:%M %p")
    return WhatsAppMessage(
        to=patient.phone,
        template=WhatsAppTemplate.APPOINTMENT_CONFIRMED,
        params={
            "patient": patient.full_name.split()[0],
            "doctor": doctor.full_name,
            "clinic": clinic.name,
            "when": when.replace(" 0", " "),
        },
    )


@router.post("/appointments", status_code=status.HTTP_201_CREATED)
async def book_appointment(
    body: AppointmentCreate,
    ctx: ClinicCtx,
    db: DbSession,
    whatsapp_sender: Annotated[WhatsAppSender, Depends(get_whatsapp_sender)],
    background: BackgroundTasks,
) -> AppointmentOut:
    """Book a time slot, or add a walk-in to today's queue (they get a token straight away)."""
    patient = await _patient(db, ctx, body.patient_id)
    doctor = await _doctor(db, ctx, body.doctor_id)
    clinic = await db.get(Clinic, ctx.clinic_id)
    zone = clinic_zone(clinic)
    now = utcnow()

    appointment = Appointment(
        clinic_id=ctx.clinic_id,
        patient_id=patient.id,
        doctor_id=doctor.id,
        kind=body.kind,
        reason=body.reason or None,
        notes=body.notes or None,
        created_by_id=ctx.user.id,
    )
    if body.kind == AppointmentKind.WALK_IN:
        appointment.start_at = now
        appointment.end_at = now + timedelta(minutes=DEFAULT_WALK_IN_MINUTES)
        appointment.visit_date = local_date(now, zone)
        appointment.status = AppointmentStatus.ARRIVED
        appointment.arrived_at = now
        appointment.token_number = await next_token(db, doctor.id, appointment.visit_date)
    else:
        appointment.start_at = body.start_at
        appointment.end_at = await _fit_slot(db, ctx, clinic, doctor, body.start_at)
        appointment.visit_date = local_date(body.start_at, zone)
        appointment.status = AppointmentStatus.BOOKED
    db.add(appointment)
    await _commit_booking(db)
    await db.refresh(appointment)

    if body.kind == AppointmentKind.SCHEDULED and patient.messaging_consent:
        message = _confirmation(patient, doctor, clinic, appointment.start_at)
        background.add_task(deliver_whatsapp, whatsapp_sender, message)
    return _out(appointment, patient, doctor)


async def _get(db: DbSession, ctx: ClinicContext, appointment_id: uuid.UUID) -> Appointment:
    appointment = await db.scalar(
        select(Appointment).where(
            Appointment.id == appointment_id, Appointment.clinic_id == ctx.clinic_id
        )
    )
    if appointment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    return appointment


@router.patch("/appointments/{appointment_id}")
async def update_appointment(
    appointment_id: uuid.UUID,
    body: AppointmentUpdate,
    ctx: ClinicCtx,
    db: DbSession,
    whatsapp_sender: Annotated[WhatsAppSender, Depends(get_whatsapp_sender)],
    background: BackgroundTasks,
) -> AppointmentOut:
    appointment = await _get(db, ctx, appointment_id)
    changes = body.model_dump(exclude_unset=True)
    moving = "start_at" in changes or "doctor_id" in changes
    if moving:
        if (
            appointment.kind != AppointmentKind.SCHEDULED
            or appointment.status != AppointmentStatus.BOOKED
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Only booked appointments can be rescheduled"
            )
        doctor = await _doctor(db, ctx, changes.get("doctor_id") or appointment.doctor_id)
        clinic = await db.get(Clinic, ctx.clinic_id)
        start_at = changes.get("start_at") or appointment.start_at
        appointment.end_at = await _fit_slot(
            db, ctx, clinic, doctor, start_at, ignore=appointment.id
        )
        appointment.start_at = start_at
        appointment.doctor_id = doctor.id
        appointment.visit_date = local_date(start_at, clinic_zone(clinic))
    if "reason" in changes:
        appointment.reason = changes["reason"] or None
    if "notes" in changes:
        appointment.notes = changes["notes"] or None
    await _commit_booking(db)
    await db.refresh(appointment)
    patient = await db.get(Patient, appointment.patient_id)
    doctor = await db.get(User, appointment.doctor_id)
    if moving and patient.messaging_consent:
        # Tell the patient the new time.
        message = _confirmation(
            patient, doctor, await db.get(Clinic, ctx.clinic_id), appointment.start_at
        )
        background.add_task(deliver_whatsapp, whatsapp_sender, message)
    return _out(appointment, patient, doctor)


@router.post("/appointments/{appointment_id}/status")
async def change_status(
    appointment_id: uuid.UUID, body: StatusChange, ctx: ClinicCtx, db: DbSession
) -> AppointmentOut:
    """Arrived (gets a queue token) → In consultation → Completed, or Cancelled / No-show."""
    appointment = await _get(db, ctx, appointment_id)
    new = body.status
    if new not in TRANSITIONS.get(appointment.status, set()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"An appointment that is {STATUS_LABELS[appointment.status]} "
            f"can't be marked {STATUS_LABELS[new]}",
        )
    clinic = await db.get(Clinic, ctx.clinic_id)
    now = utcnow()
    if new == AppointmentStatus.ARRIVED:
        if appointment.visit_date != local_date(now, clinic_zone(clinic)):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Only today's appointments can be checked in"
            )
        appointment.arrived_at = now
        if appointment.token_number is None:
            appointment.token_number = await next_token(
                db, appointment.doctor_id, appointment.visit_date
            )
    elif new == AppointmentStatus.IN_CONSULTATION:
        appointment.started_at = now
    elif new == AppointmentStatus.COMPLETED:
        appointment.completed_at = now
    elif new == AppointmentStatus.CANCELLED:
        appointment.cancelled_at = now
    appointment.status = new
    await db.commit()
    await db.refresh(appointment)
    patient = await db.get(Patient, appointment.patient_id)
    return _out(appointment, patient, await db.get(User, appointment.doctor_id))
