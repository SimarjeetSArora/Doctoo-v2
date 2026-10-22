import uuid
from datetime import date, datetime, time
from typing import Annotated, Self

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints, model_validator

from app.models import AppointmentKind, AppointmentStatus

Reason = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class SessionIn(BaseModel):
    weekday: int = Field(ge=0, le=6)  # 0 = Monday
    start_time: time
    end_time: time
    slot_minutes: int = Field(default=15, ge=5, le=120)

    @model_validator(mode="after")
    def _order(self) -> Self:
        if self.end_time <= self.start_time:
            raise ValueError("A session must end after it starts")
        return self


class SessionOut(SessionIn):
    pass


class ScheduleUpdate(BaseModel):
    """Replaces all of a doctor's working sessions."""

    sessions: list[SessionIn] = Field(max_length=42)

    @model_validator(mode="after")
    def _no_overlaps(self) -> Self:
        by_day: dict[int, list[SessionIn]] = {}
        for session in self.sessions:
            by_day.setdefault(session.weekday, []).append(session)
        for sessions in by_day.values():
            sessions.sort(key=lambda s: s.start_time)
            for earlier, later in zip(sessions, sessions[1:], strict=False):
                if later.start_time < earlier.end_time:
                    raise ValueError("Sessions on the same day can't overlap")
        return self


class DoctorOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    sessions: list[SessionOut]


class AppointmentCreate(BaseModel):
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    kind: AppointmentKind = AppointmentKind.SCHEDULED
    start_at: AwareDatetime | None = None  # required for scheduled; walk-ins start now
    reason: Reason | None = None
    notes: Notes | None = None

    @model_validator(mode="after")
    def _time(self) -> Self:
        if self.kind == AppointmentKind.SCHEDULED and self.start_at is None:
            raise ValueError("Choose a time for the appointment")
        return self


class AppointmentUpdate(BaseModel):
    """Reschedule (time / doctor) or edit the reason and notes."""

    doctor_id: uuid.UUID | None = None
    start_at: AwareDatetime | None = None
    reason: Reason | None = None
    notes: Notes | None = None


class StatusChange(BaseModel):
    status: AppointmentStatus


class AppointmentOut(BaseModel):
    id: uuid.UUID
    kind: AppointmentKind
    status: AppointmentStatus
    start_at: datetime
    end_at: datetime
    visit_date: date
    token_number: int | None
    reason: str | None
    notes: str | None
    patient_id: uuid.UUID
    patient_name: str
    patient_phone: str
    doctor_id: uuid.UUID
    doctor_name: str
    arrived_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime


class SlotOut(BaseModel):
    start_at: datetime
    end_at: datetime
    available: bool
