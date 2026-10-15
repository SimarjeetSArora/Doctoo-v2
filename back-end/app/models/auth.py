"""Tables that support login: sessions, password resets, invitations and one-time codes.

Every token here is stored only as a SHA-256 hash. The real token exists only in the user's
cookie or email, so a leaked database can't be used to log in.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, str_enum
from app.models.clinic import Clinic
from app.models.user import Role, User


class UserSession(Base):
    """One logged-in device. Holds the refresh token; revoking it logs that device out."""

    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(500))

    user: Mapped[User] = relationship()


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Invitation(TenantMixin, Base):
    """An owner inviting someone to join their clinic with a role, by email OR mobile number."""

    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint("(email IS NULL) <> (phone IS NULL)", name="email_xor_phone"),
    )

    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(20), index=True)  # E.164
    role: Mapped[Role] = mapped_column(str_enum(Role, 20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    clinic: Mapped[Clinic] = relationship()
    invited_by: Mapped[User] = relationship()

    @property
    def sent_to(self) -> str:
        return self.email or self.phone or ""


class OtpChannel(enum.StrEnum):
    EMAIL = "email"
    PHONE = "phone"


class OtpPurpose(enum.StrEnum):
    REGISTER = "register"  # prove a new email belongs to you (sign-up, accepting an invite)
    LOGIN = "login"  # log in without a password


class VerificationCode(Base):
    """A 6-digit one-time code sent by email or SMS.

    Only a keyed hash of the code is stored. Each code allows a few attempts and expires quickly.
    """

    __tablename__ = "verification_codes"
    __table_args__ = (
        Index("ix_verification_codes_target_purpose", "channel", "target", "purpose"),
    )

    channel: Mapped[OtpChannel] = mapped_column(str_enum(OtpChannel, 10))
    target: Mapped[str] = mapped_column(String(255))  # email address or E.164 phone number
    purpose: Mapped[OtpPurpose] = mapped_column(str_enum(OtpPurpose, 20))
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
