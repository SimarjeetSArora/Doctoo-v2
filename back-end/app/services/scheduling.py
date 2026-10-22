"""Time-slot logic. Working hours are in the clinic's local time; the database stores UTC."""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ACTIVE_STATUSES,
    Appointment,
    AppointmentKind,
    Clinic,
    ClinicMember,
    DoctorSession,
    Role,
    Salutation,
    User,
)

DEFAULT_WALK_IN_MINUTES = 15


def clinic_zone(clinic: Clinic) -> ZoneInfo:
    return ZoneInfo(clinic.timezone or "Asia/Kolkata")


def local_date(moment: datetime, zone: ZoneInfo) -> date:
    return moment.astimezone(zone).date()


def day_bounds(day: date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    """Start and end of a local day, in UTC."""
    start = datetime.combine(day, datetime.min.time(), zone)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


def is_doctor(member: ClinicMember, user: User) -> bool:
    """Members who see patients: doctors, plus owners who are doctors themselves."""
    return member.role == Role.DOCTOR or (
        member.role == Role.OWNER and user.salutation == Salutation.DR
    )


async def clinic_doctors(
    db: AsyncSession, clinic_ids: Iterable[uuid.UUID]
) -> list[tuple[ClinicMember, User]]:
    rows = await db.execute(
        select(ClinicMember, User)
        .join(User, User.id == ClinicMember.user_id)
        .where(ClinicMember.clinic_id.in_(list(clinic_ids)), ClinicMember.is_active, User.is_active)
        .order_by(User.first_name, User.last_name)
    )
    return [(m, u) for m, u in rows.all() if is_doctor(m, u)]


async def doctor_sessions(
    db: AsyncSession, clinic_id: uuid.UUID, doctor_id: uuid.UUID
) -> list[DoctorSession]:
    rows = await db.scalars(
        select(DoctorSession)
        .where(DoctorSession.clinic_id == clinic_id, DoctorSession.doctor_id == doctor_id)
        .order_by(DoctorSession.weekday, DoctorSession.start_time)
    )
    return list(rows)


def session_at(
    sessions: list[DoctorSession], start: datetime, zone: ZoneInfo
) -> DoctorSession | None:
    """The working session a booking starting at `start` fits into (whole slot inside it)."""
    local = start.astimezone(zone)
    for session in sessions:
        if session.weekday != local.weekday():
            continue
        begins = datetime.combine(local.date(), session.start_time, zone)
        ends = datetime.combine(local.date(), session.end_time, zone)
        if begins <= local and local + timedelta(minutes=session.slot_minutes) <= ends:
            return session
    return None


@dataclass
class Slot:
    start_at: datetime
    end_at: datetime
    available: bool


def build_slots(
    sessions: list[DoctorSession],
    day: date,
    zone: ZoneInfo,
    busy: list[tuple[datetime, datetime]],
    now: datetime,
) -> list[Slot]:
    slots = []
    for session in sessions:
        if session.weekday != day.weekday():
            continue
        step = timedelta(minutes=session.slot_minutes)
        start = datetime.combine(day, session.start_time, zone)
        session_end = datetime.combine(day, session.end_time, zone)
        while start + step <= session_end:
            end = start + step
            free = start >= now and not any(
                start < b_end and end > b_start for b_start, b_end in busy
            )
            slots.append(Slot(start.astimezone(UTC), end.astimezone(UTC), free))
            start = end
    return sorted(slots, key=lambda s: s.start_at)


async def busy_times(
    db: AsyncSession,
    doctor_id: uuid.UUID,
    start: datetime,
    end: datetime,
    ignore: uuid.UUID | None = None,
) -> list[tuple[datetime, datetime]]:
    """Times already taken by the doctor's active scheduled appointments."""
    query = select(Appointment.start_at, Appointment.end_at).where(
        Appointment.doctor_id == doctor_id,
        Appointment.kind == AppointmentKind.SCHEDULED,
        Appointment.status.in_(ACTIVE_STATUSES),
        Appointment.start_at < end,
        Appointment.end_at > start,
    )
    if ignore:
        query = query.where(Appointment.id != ignore)
    return [(s, e) for s, e in (await db.execute(query)).all()]


async def next_token(db: AsyncSession, doctor_id: uuid.UUID, visit_date: date) -> int:
    """The next queue number for the doctor's day. A transaction lock stops two arrivals at the
    same moment from getting the same number."""
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"{doctor_id}:{visit_date}"))))
    current = await db.scalar(
        select(func.max(Appointment.token_number)).where(
            Appointment.doctor_id == doctor_id, Appointment.visit_date == visit_date
        )
    )
    return (current or 0) + 1
