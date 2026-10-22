import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.models import AppointmentKind, AppointmentStatus, Gender
from app.schemas.auth import OtpCode
from app.schemas.common import Phone


class PatientOtpRequest(BaseModel):
    phone: Phone
    delivery: Literal["whatsapp", "sms"] = "whatsapp"


class PatientLoginRequest(BaseModel):
    phone: Phone
    code: OtpCode


class ProfileSummary(BaseModel):
    id: uuid.UUID
    name: str  # full name once verified, masked ("Simarjeet A.") before
    verified: bool
    can_verify: bool  # False when the clinic hasn't recorded a date of birth
    clinic_count: int


class PatientMe(BaseModel):
    phone: str
    profiles: list[ProfileSummary]


class VerifyProfileRequest(BaseModel):
    date_of_birth: date


class ClinicCard(BaseModel):
    id: uuid.UUID
    name: str
    phone: str | None
    email: str | None
    address: str | None
    city: str | None
    state: str | None
    pincode: str | None
    patient_since: date


class DoctorCard(BaseModel):
    name: str
    clinic_id: uuid.UUID
    clinic_name: str


class AppointmentCard(BaseModel):
    id: uuid.UUID
    kind: AppointmentKind
    status: AppointmentStatus
    start_at: datetime
    token_number: int | None
    reason: str | None
    doctor_name: str
    clinic_name: str


class PrescriptionCard(BaseModel):
    """Filled in once doctors can write prescriptions."""

    id: uuid.UUID


class ReportCard(BaseModel):
    """Filled in once clinics can upload reports."""

    id: uuid.UUID


class ProfileDetails(BaseModel):
    id: uuid.UUID
    full_name: str
    date_of_birth: date | None
    age: int | None
    gender: Gender | None
    blood_group: str | None
    clinics: list[ClinicCard]
    doctors: list[DoctorCard]
    appointments: list[AppointmentCard]  # newest first
    prescriptions: list[PrescriptionCard]
    reports: list[ReportCard]
