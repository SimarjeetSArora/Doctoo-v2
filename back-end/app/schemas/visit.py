import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints

from app.models import Gender, VisitStatus


def _blank_to_none(value):
    return None if isinstance(value, str) and not value.strip() else value


Blankable = BeforeValidator(_blank_to_none)
LongText = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)] | None, Blankable
]


def _short(max_length: int, required: bool = False):
    text = Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)
    ]
    return text if required else Annotated[text | None, Blankable]


class Vitals(BaseModel):
    """All optional; out-of-range values are rejected as likely typos."""

    bp_systolic: int | None = Field(default=None, ge=50, le=260)  # mmHg
    bp_diastolic: int | None = Field(default=None, ge=30, le=160)
    pulse: int | None = Field(default=None, ge=20, le=250)  # beats/min
    temperature_f: float | None = Field(default=None, ge=90, le=110)  # °F
    spo2: int | None = Field(default=None, ge=50, le=100)  # %
    respiratory_rate: int | None = Field(default=None, ge=5, le=80)  # breaths/min
    blood_sugar: int | None = Field(default=None, ge=20, le=800)  # mg/dL
    weight_kg: float | None = Field(default=None, ge=0.5, le=400)
    height_cm: float | None = Field(default=None, ge=30, le=250)


class PrescriptionItemIn(BaseModel):
    medicine: _short(200, required=True)
    dose: _short(50, required=True)  # 1-0-1, 1 tsp, 2 puffs…
    timing: _short(50) = None  # After food…
    duration: _short(50) = None  # 5 days…
    instructions: _short(300) = None


class PrescriptionItemOut(PrescriptionItemIn):
    pass


class VisitUpdate(BaseModel):
    """Only the fields sent are changed. `items` replaces the whole prescription."""

    vitals: Vitals | None = None
    complaints: LongText = None
    examination: LongText = None
    diagnosis: LongText = None
    advice: LongText = None
    follow_up_date: Annotated[date | None, Blankable] = None
    items: list[PrescriptionItemIn] | None = Field(default=None, max_length=40)


class VisitPatient(BaseModel):
    id: uuid.UUID
    full_name: str
    phone: str
    age: int | None
    gender: Gender | None
    blood_group: str | None
    notes: str | None  # allergies etc. — shown prominently to the doctor
    messaging_consent: bool


class VisitOut(BaseModel):
    id: uuid.UUID
    status: VisitStatus
    appointment_id: uuid.UUID | None
    patient: VisitPatient
    doctor_id: uuid.UUID
    doctor_name: str
    vitals: Vitals
    complaints: str | None
    examination: str | None
    diagnosis: str | None
    advice: str | None
    follow_up_date: date | None
    items: list[PrescriptionItemOut]
    prescription_number: str | None  # "RX-2026-00001" once finished
    created_at: datetime
    completed_at: datetime | None
    can_edit: bool  # still open, and you're its doctor or the clinic owner


class VisitSummary(BaseModel):
    id: uuid.UUID
    status: VisitStatus
    doctor_name: str
    diagnosis: str | None
    medicines: list[str]
    prescription_number: str | None
    created_at: datetime
    completed_at: datetime | None


class ShareResult(BaseModel):
    sent_to: str
    link_expires_at: datetime


class MedicineSuggestion(BaseModel):
    name: str
    times_used: int
