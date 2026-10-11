import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, str_enum
from app.models.patient import Patient
from app.models.user import User


class AppointmentStatus(enum.StrEnum):
    BOOKED = "booked"
    ARRIVED = "arrived"
    IN_CONSULTATION = "in_consultation"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"


class Appointment(TenantMixin, Base):
    __tablename__ = "appointments"
    # The calendar asks "what does doctor X have between these times?" — index exactly that.
    __table_args__ = (
        Index("ix_appointments_clinic_doctor_start", "clinic_id", "doctor_id", "start_at"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[AppointmentStatus] = mapped_column(
        str_enum(AppointmentStatus, 20),
        default=AppointmentStatus.BOOKED,
    )
    reason: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)

    patient: Mapped[Patient] = relationship()
    doctor: Mapped[User] = relationship()
