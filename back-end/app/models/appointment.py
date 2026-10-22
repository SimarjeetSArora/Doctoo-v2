import enum
import uuid
from datetime import date, datetime, time

from sqlalchemy import DDL, CheckConstraint, DateTime, ForeignKey, Index, String, Text, event, text
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


# Appointments that still hold the doctor's time.
ACTIVE_STATUSES = (
    AppointmentStatus.BOOKED,
    AppointmentStatus.ARRIVED,
    AppointmentStatus.IN_CONSULTATION,
)


class AppointmentKind(enum.StrEnum):
    SCHEDULED = "scheduled"  # booked for a time slot
    WALK_IN = "walk_in"  # came without booking; gets a token in the day's queue


class Appointment(TenantMixin, Base):
    """A booked slot or a walk-in.

    Double booking is prevented by the database itself: an exclusion constraint (created in the
    migration) forbids two active scheduled appointments of one doctor whose times overlap.
    """

    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_clinic_doctor_start", "clinic_id", "doctor_id", "start_at"),
        # One token number per doctor per day.
        Index(
            "uq_appointments_doctor_day_token",
            "doctor_id",
            "visit_date",
            "token_number",
            unique=True,
            postgresql_where=text("token_number IS NOT NULL"),
        ),
        CheckConstraint("end_at > start_at", name="ends_after_start"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[AppointmentKind] = mapped_column(
        str_enum(AppointmentKind, 10), default=AppointmentKind.SCHEDULED
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # The day in the clinic's time zone (tokens and day views are per local day).
    visit_date: Mapped[date] = mapped_column(index=True)
    status: Mapped[AppointmentStatus] = mapped_column(
        str_enum(AppointmentStatus, 20),
        default=AppointmentStatus.BOOKED,
    )
    # Queue number for the day, given on arrival (walk-ins get one straight away).
    token_number: Mapped[int | None]
    reason: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)

    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    patient: Mapped[Patient] = relationship()
    doctor: Mapped[User] = relationship(foreign_keys=[doctor_id])


class DoctorSession(TenantMixin, Base):
    """A block of working hours, e.g. Monday 10:00–13:00 in 15-minute slots.

    A doctor can have several per day (morning and evening OPD are common).
    """

    __tablename__ = "doctor_sessions"
    __table_args__ = (
        Index("ix_doctor_sessions_clinic_doctor", "clinic_id", "doctor_id"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="valid_weekday"),
        CheckConstraint("end_time > start_time", name="ends_after_start"),
        CheckConstraint("slot_minutes BETWEEN 5 AND 120", name="valid_slot"),
    )

    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    weekday: Mapped[int]  # 0 = Monday … 6 = Sunday
    start_time: Mapped[time]
    end_time: Mapped[time]
    slot_minutes: Mapped[int] = mapped_column(default=15)


# The no-double-booking rule as raw SQL, so databases built straight from the models (tests) get
# it too. Real databases get it from the Alembic migration.
NO_DOUBLE_BOOKING_SQL = (
    "ALTER TABLE appointments ADD CONSTRAINT ex_appointments_no_double_booking "
    "EXCLUDE USING gist (doctor_id WITH =, tstzrange(start_at, end_at) WITH &&) "
    "WHERE (kind = 'scheduled' AND status IN ('booked', 'arrived', 'in_consultation'))"
)
event.listen(
    Appointment.__table__, "before_create", DDL("CREATE EXTENSION IF NOT EXISTS btree_gist")
)
event.listen(Appointment.__table__, "after_create", DDL(NO_DOUBLE_BOOKING_SQL))
