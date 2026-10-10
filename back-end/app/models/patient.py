import enum
from datetime import date

from sqlalchemy import Enum, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TenantMixin


class Gender(enum.StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Patient(TenantMixin, SoftDeleteMixin, Base):
    __tablename__ = "patients"
    # Reception searches patients by phone number constantly, so index it per clinic.
    __table_args__ = (Index("ix_patients_clinic_id_phone", "clinic_id", "phone"),)

    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    date_of_birth: Mapped[date | None]
    gender: Mapped[Gender | None] = mapped_column(
        Enum(Gender, native_enum=False, length=10, values_callable=lambda e: [m.value for m in e])
    )
    blood_group: Mapped[str | None] = mapped_column(String(5))
    address: Mapped[str | None] = mapped_column(String(500))
    abha_number: Mapped[str | None] = mapped_column(String(20))  # Ayushman Bharat Health Account ID
    notes: Mapped[str | None] = mapped_column(Text)  # allergies, chronic conditions, etc.
