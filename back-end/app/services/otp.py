"""One-time codes sent by email or SMS.

Rules: 6 digits, valid 10 minutes, 5 wrong attempts per code, 60 s between sends, at most
5 codes per hour per email/number, single use. Codes are stored as an HMAC keyed with SECRET_KEY,
so a leaked database can't be used to brute-force them offline.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import OtpChannel, OtpPurpose, VerificationCode
from app.services.auth import utcnow

CODE_TTL = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_SENDS_PER_HOUR = 5
MAX_ATTEMPTS = 5


class OtpError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _hash(channel: OtpChannel, target: str, purpose: OtpPurpose, code: str) -> str:
    key = get_settings().secret_key.encode()
    message = f"{channel}:{purpose}:{target}:{code}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _same_target(channel: OtpChannel, target: str, purpose: OtpPurpose):
    return (
        VerificationCode.channel == channel,
        VerificationCode.target == target,
        VerificationCode.purpose == purpose,
    )


async def issue_code(
    db: AsyncSession, channel: OtpChannel, target: str, purpose: OtpPurpose
) -> str:
    """Creates a new code (replacing any unused one) and returns it for sending."""
    now = utcnow()
    recent = (
        await db.scalars(
            select(VerificationCode)
            .where(
                *_same_target(channel, target, purpose),
                VerificationCode.created_at > now - timedelta(hours=1),
            )
            .order_by(VerificationCode.created_at.desc())
        )
    ).all()
    if recent and recent[0].created_at > now - RESEND_COOLDOWN:
        wait = int((recent[0].created_at + RESEND_COOLDOWN - now).total_seconds()) + 1
        raise OtpError(429, f"Please wait {wait} seconds before requesting a new code")
    if len(recent) >= MAX_SENDS_PER_HOUR:
        raise OtpError(429, "Too many codes requested. Please try again in an hour.")

    # Only the newest code works.
    await db.execute(
        update(VerificationCode)
        .where(*_same_target(channel, target, purpose), VerificationCode.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        VerificationCode(
            channel=channel,
            target=target,
            purpose=purpose,
            code_hash=_hash(channel, target, purpose, code),
            expires_at=now + CODE_TTL,
        )
    )
    return code


async def consume_code(
    db: AsyncSession, channel: OtpChannel, target: str, purpose: OtpPurpose, code: str
) -> None:
    """Marks the code as used, or raises OtpError. Wrong attempts are saved immediately."""
    record = await db.scalar(
        select(VerificationCode)
        .where(*_same_target(channel, target, purpose), VerificationCode.consumed_at.is_(None))
        .order_by(VerificationCode.created_at.desc())
    )
    if record is None or record.expires_at <= utcnow():
        raise OtpError(400, "This code has expired. Please request a new one.")
    if record.attempts >= MAX_ATTEMPTS:
        raise OtpError(400, "Too many wrong attempts. Please request a new code.")
    if not hmac.compare_digest(record.code_hash, _hash(channel, target, purpose, code)):
        record.attempts += 1
        await db.commit()
        left = MAX_ATTEMPTS - record.attempts
        hint = f" {left} attempt{'s' if left != 1 else ''} left." if left else ""
        raise OtpError(400, f"Incorrect verification code.{hint}")
    record.consumed_at = utcnow()
