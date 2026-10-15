import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, str_enum


class Salutation(enum.StrEnum):
    DR = "Dr."
    MR = "Mr."
    MRS = "Mrs."
    MS = "Ms."
    MISS = "Miss"
    PROF = "Prof."


class User(Base):
    """A clinic staff login account (owner, doctor, receptionist).

    One user can belong to several clinics (e.g. a visiting doctor). Patients are NOT users;
    they get their own phone-OTP accounts in the patient portal phase.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True)  # always stored lowercase
    salutation: Mapped[Salutation | None] = mapped_column(str_enum(Salutation, 10))
    first_name: Mapped[str] = mapped_column(String(100))
    middle_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    # International (E.164) format, e.g. +919876543210. Unique: it can be used to log in.
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    # Set once they prove they own the email (sign-up code, invite link or password-reset link).
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set once they verify the phone number by OTP (coming later).
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(default=True)

    memberships: Mapped[list["ClinicMember"]] = relationship(back_populates="user")

    @property
    def full_name(self) -> str:
        """Display name, e.g. "Dr. Simarjeet Singh Arora"."""
        parts = (self.salutation, self.first_name, self.middle_name, self.last_name)
        return " ".join(part for part in parts if part)


class Role(enum.StrEnum):
    OWNER = "owner"
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"


class ClinicMember(TenantMixin, Base):
    """Links a user to a clinic with a role. Permissions are decided by this role."""

    __tablename__ = "clinic_members"
    __table_args__ = (UniqueConstraint("clinic_id", "user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[Role] = mapped_column(str_enum(Role, 20))
    is_active: Mapped[bool] = mapped_column(default=True)

    clinic: Mapped["Clinic"] = relationship(back_populates="members")  # noqa: F821
    user: Mapped[User] = relationship(back_populates="memberships")
