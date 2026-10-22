"""Consultations (visits) and the prescriptions written in them."""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, str_enum


class VisitStatus(enum.StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"  # finished and locked: medical records aren't silently changed


class Visit(TenantMixin, Base):
    """One consultation: vitals, notes, diagnosis and the prescription."""

    __tablename__ = "visits"
    __table_args__ = (
        # Prescription numbers run per clinic: RX-2026-00001, RX-2026-00002 …
        Index(
            "uq_visits_clinic_prescription_number",
            "clinic_id",
            "prescription_number",
            unique=True,
            postgresql_where=text("prescription_number IS NOT NULL"),
        ),
    )

    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("appointments.id"), unique=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[VisitStatus] = mapped_column(
        str_enum(VisitStatus, 20), default=VisitStatus.IN_PROGRESS
    )
    # Blood pressure, pulse, temperature, SpO2, weight, height… (validated by the API schema)
    vitals: Mapped[dict] = mapped_column(JSONB, default=dict)
    complaints: Mapped[str | None] = mapped_column(Text)
    examination: Mapped[str | None] = mapped_column(Text)
    diagnosis: Mapped[str | None] = mapped_column(Text)
    advice: Mapped[str | None] = mapped_column(Text)
    follow_up_date: Mapped[date | None]
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prescription_number: Mapped[int | None]
    # Secure link for sharing the prescription PDF (WhatsApp); only the hash is stored.
    share_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    share_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["PrescriptionItem"]] = relationship(
        back_populates="visit",
        cascade="all, delete-orphan",
        order_by="PrescriptionItem.position",
        lazy="selectin",
    )


class PrescriptionItem(Base):
    """One medicine line: Paracetamol 650 mg · 1-0-1 · After food · 5 days."""

    __tablename__ = "prescription_items"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visits.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    medicine: Mapped[str] = mapped_column(String(200))
    dose: Mapped[str] = mapped_column(String(50))  # e.g. 1-0-1, 1 tsp, 2 puffs
    timing: Mapped[str | None] = mapped_column(String(50))  # e.g. After food
    duration: Mapped[str | None] = mapped_column(String(50))  # e.g. 5 days
    instructions: Mapped[str | None] = mapped_column(String(300))

    visit: Mapped[Visit] = relationship(back_populates="items")


class Medicine(TenantMixin, Base):
    """Medicines this clinic has prescribed — used to suggest names while typing."""

    __tablename__ = "medicines"
    __table_args__ = (Index("uq_medicines_clinic_key", "clinic_id", "name_key", unique=True),)

    name: Mapped[str] = mapped_column(String(200))
    name_key: Mapped[str] = mapped_column(String(200))  # lowercase, single-spaced
    times_used: Mapped[int] = mapped_column(default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
