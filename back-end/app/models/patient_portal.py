"""Patient app accounts: one per mobile number, logged in with a one-time code.

A phone number can belong to several patient records: the same person at different clinics, and
family members sharing a number. The account sees all of them, grouped into profiles.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PatientAccount(Base):
    __tablename__ = "patient_accounts"

    phone: Mapped[str] = mapped_column(String(20), unique=True)  # E.164
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Wrong date-of-birth answers, to stop guessing.
    dob_failed_attempts: Mapped[int] = mapped_column(default=0)
    dob_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PatientSession(Base):
    """One logged-in device in the patient app (refresh token stored hashed)."""

    __tablename__ = "patient_sessions"

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patient_accounts.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(500))
