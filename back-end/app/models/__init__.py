# Import every model here so Alembic can discover all tables.
from app.models.appointment import (
    ACTIVE_STATUSES,
    Appointment,
    AppointmentKind,
    AppointmentStatus,
    DoctorSession,
)
from app.models.auth import (
    Invitation,
    OtpChannel,
    OtpPurpose,
    PasswordResetToken,
    UserSession,
    VerificationCode,
)
from app.models.base import Base
from app.models.clinic import Clinic
from app.models.patient import Gender, Patient
from app.models.patient_portal import PatientAccount, PatientSession
from app.models.user import ClinicMember, Role, Salutation, User
from app.models.visit import Medicine, PrescriptionItem, Visit, VisitStatus

__all__ = [
    "ACTIVE_STATUSES",
    "Appointment",
    "AppointmentKind",
    "AppointmentStatus",
    "Base",
    "Clinic",
    "DoctorSession",
    "ClinicMember",
    "Gender",
    "Invitation",
    "Medicine",
    "OtpChannel",
    "OtpPurpose",
    "PasswordResetToken",
    "Patient",
    "PatientAccount",
    "PatientSession",
    "PrescriptionItem",
    "Role",
    "Salutation",
    "User",
    "UserSession",
    "VerificationCode",
    "Visit",
    "VisitStatus",
]
