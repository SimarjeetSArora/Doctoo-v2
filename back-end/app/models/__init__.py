# Import every model here so Alembic can discover all tables.
from app.models.appointment import Appointment, AppointmentStatus
from app.models.base import Base
from app.models.clinic import Clinic
from app.models.patient import Gender, Patient
from app.models.user import ClinicMember, Role, User

__all__ = [
    "Appointment",
    "AppointmentStatus",
    "Base",
    "Clinic",
    "ClinicMember",
    "Gender",
    "Patient",
    "Role",
    "User",
]
