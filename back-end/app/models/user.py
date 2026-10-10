import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin


class User(Base):
    """A login account. One user can belong to several clinics (e.g. a visiting doctor)."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(20))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)

    memberships: Mapped[list["ClinicMember"]] = relationship(back_populates="user")


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
    # Stored as plain text (not a Postgres enum) so adding roles later needs no tricky migration.
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e])
    )
    is_active: Mapped[bool] = mapped_column(default=True)

    clinic: Mapped["Clinic"] = relationship(back_populates="members")  # noqa: F821
    user: Mapped[User] = relationship(back_populates="memberships")
