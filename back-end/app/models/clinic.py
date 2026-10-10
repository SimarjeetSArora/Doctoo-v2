from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Clinic(Base):
    """A tenant: one clinic/practice using Doctoo."""

    __tablename__ = "clinics"

    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    pincode: Mapped[str | None] = mapped_column(String(10))
    gstin: Mapped[str | None] = mapped_column(String(15))
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata")

    members: Mapped[list["ClinicMember"]] = relationship(back_populates="clinic")  # noqa: F821
