"""Patient app logic: sessions, and grouping a phone number's records into profiles."""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from fastapi import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, generate_token, hash_token
from app.models import Patient, PatientAccount, PatientSession
from app.schemas.auth import TokenResponse
from app.services.auth import utcnow

PATIENT_REFRESH_COOKIE = "doctoo_patient_refresh"
_PATIENT_COOKIE_PATH = "/api/v1/patient/auth"
PATIENT_TOKEN_TYPE = "patient"

DOB_MAX_ATTEMPTS = 5
DOB_LOCK = timedelta(hours=1)


async def start_patient_session(
    db: AsyncSession, account: PatientAccount, response: Response, user_agent: str | None
) -> TokenResponse:
    settings = get_settings()
    refresh_token = generate_token()
    db.add(
        PatientSession(
            account_id=account.id,
            token_hash=hash_token(refresh_token),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
            user_agent=user_agent[:500] if user_agent else None,
        )
    )
    await db.commit()
    response.set_cookie(
        PATIENT_REFRESH_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path=_PATIENT_COOKIE_PATH,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
    )
    return TokenResponse(access_token=create_access_token(account.id, PATIENT_TOKEN_TYPE))


def clear_patient_cookie(response: Response) -> None:
    response.delete_cookie(PATIENT_REFRESH_COOKIE, path=_PATIENT_COOKIE_PATH)


async def get_active_patient_session(db: AsyncSession, token: str | None) -> PatientSession | None:
    if not token:
        return None
    session = await db.scalar(
        select(PatientSession).where(PatientSession.token_hash == hash_token(token))
    )
    if session is None or session.revoked_at is not None or session.expires_at <= utcnow():
        return None
    return session


async def records_for_phone(db: AsyncSession, phone: str) -> list[Patient]:
    """Every active patient record with this number, at any clinic."""
    rows = await db.scalars(
        select(Patient)
        .where(Patient.phone == phone, Patient.deleted_at.is_(None))
        .order_by(Patient.created_at)
    )
    return list(rows)


@dataclass
class Profile:
    """One person: their records at one or more clinics (same name + date of birth)."""

    records: list[Patient]

    @property
    def id(self) -> uuid.UUID:
        return self.records[0].id  # oldest record

    @property
    def full_name(self) -> str:
        return self.records[0].full_name

    @property
    def date_of_birth(self) -> date | None:
        return self.records[0].date_of_birth

    @property
    def verified(self) -> bool:
        return any(r.portal_verified_at for r in self.records)

    @property
    def masked_name(self) -> str:
        """Name shown before the date-of-birth check: Simarjeet Singh Arora -> Simarjeet A."""
        words = self.full_name.split()
        return words[0] if len(words) == 1 else f"{words[0]} {words[-1][0]}."


def group_profiles(records: list[Patient]) -> list[Profile]:
    groups: dict[tuple[str, date | None], list[Patient]] = {}
    for record in records:
        key = (" ".join(record.full_name.lower().split()), record.date_of_birth)
        groups.setdefault(key, []).append(record)
    return [Profile(records) for records in groups.values()]


async def profiles_for_phone(db: AsyncSession, phone: str) -> list[Profile]:
    return group_profiles(await records_for_phone(db, phone))
