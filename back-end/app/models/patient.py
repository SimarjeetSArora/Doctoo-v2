import enum
from datetime import date, datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TenantMixin, str_enum


class Gender(enum.StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Patient(TenantMixin, SoftDeleteMixin, Base):
    __tablename__ = "patients"
    # Reception searches patients by phone number constantly, so index it per clinic.
    __table_args__ = (
        Index("ix_patients_clinic_id_phone", "clinic_id", "phone"),
        # The patient app finds every record (all clinics, all family members) by phone.
        Index("ix_patients_phone", "phone"),
    )

    full_name: Mapped[str] = mapped_column(String(200))
    # Mobile number in E.164 (+919876543210). Family members often share one.
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    date_of_birth: Mapped[date | None]
    gender: Mapped[Gender | None] = mapped_column(str_enum(Gender, 10))
    blood_group: Mapped[str | None] = mapped_column(String(5))
    address: Mapped[str | None] = mapped_column(String(500))
    abha_number: Mapped[str | None] = mapped_column(String(20))  # Ayushman Bharat Health Account ID
    notes: Mapped[str | None] = mapped_column(Text)  # allergies, chronic conditions, etc.

    # Consent to receive WhatsApp/SMS messages (prescriptions, reminders) — needed under DPDP.
    messaging_consent: Mapped[bool] = mapped_column(default=False)
    messaging_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set once the patient confirmed this record in the patient app (date-of-birth check).
    portal_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
