import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, generate_token, hash_token
from app.models import Clinic, ClinicMember, OtpChannel, Role, User, UserSession
from app.schemas.auth import TokenResponse

REFRESH_COOKIE = "doctoo_refresh"
_REFRESH_COOKIE_PATH = "/api/v1/auth"  # browser only sends it to auth endpoints


def utcnow() -> datetime:
    return datetime.now(UTC)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email.lower()))


async def get_user_by_phone(db: AsyncSession, phone: str) -> User | None:
    return await db.scalar(select(User).where(User.phone == phone))


async def get_user_by_identifier(db: AsyncSession, channel: OtpChannel, target: str) -> User | None:
    """Finds a user by email address or (E.164) mobile number."""
    if channel == OtpChannel.EMAIL:
        return await get_user_by_email(db, target)
    return await get_user_by_phone(db, target)


def mark_verified(user: User, channel: OtpChannel) -> None:
    """Records that the user just proved they own this email address / phone number."""
    if channel == OtpChannel.EMAIL:
        user.email_verified_at = user.email_verified_at or utcnow()
    else:
        user.phone_verified_at = user.phone_verified_at or utcnow()


async def create_clinic_with_owner(db: AsyncSession, user: User, clinic: Clinic) -> Clinic:
    db.add(clinic)
    await db.flush()  # assigns clinic.id
    db.add(ClinicMember(clinic_id=clinic.id, user_id=user.id, role=Role.OWNER))
    return clinic


async def start_session(
    db: AsyncSession, user: User, response: Response, user_agent: str | None
) -> TokenResponse:
    """Logs the user in on this device: stores a session and sets the refresh cookie."""
    settings = get_settings()
    refresh_token = generate_token()
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
            user_agent=user_agent[:500] if user_agent else None,
        )
    )
    await db.commit()
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path=_REFRESH_COOKIE_PATH,
        httponly=True,  # JavaScript can't read it, so XSS can't steal it
        secure=settings.is_production,  # HTTPS-only in production
        samesite="lax",
    )
    return TokenResponse(access_token=create_access_token(user.id))


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=_REFRESH_COOKIE_PATH)


async def get_active_session(db: AsyncSession, refresh_token: str | None) -> UserSession | None:
    if not refresh_token:
        return None
    session = await db.scalar(
        select(UserSession).where(UserSession.token_hash == hash_token(refresh_token))
    )
    if session is None or session.revoked_at is not None or session.expires_at <= utcnow():
        return None
    return session


async def revoke_all_sessions(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
