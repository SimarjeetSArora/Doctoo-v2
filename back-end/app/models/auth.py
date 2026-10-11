"""Tables that support login: sessions, password-reset links and staff invitations.

Every token here is stored only as a SHA-256 hash. The real token exists only in the user's
cookie or email, so a leaked database can't be used to log in.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
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
    """An owner inviting someone (by email) to join their clinic with a role."""

    __tablename__ = "invitations"

    email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[Role] = mapped_column(str_enum(Role, 20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    clinic: Mapped[Clinic] = relationship()
    invited_by: Mapped[User] = relationship()
