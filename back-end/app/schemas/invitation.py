import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, model_validator

from app.models import OtpChannel, Role
from app.schemas.auth import OtpCode
from app.schemas.common import Email, Password, PersonDetails, Phone


class InvitationCreate(BaseModel):
    """Invite by email OR mobile number (with country code), not both."""

    email: Email | None = None
    phone: Phone | None = None
    role: Role

    @model_validator(mode="after")
    def _one_contact(self) -> Self:
        if (self.email is None) == (self.phone is None):
            raise ValueError("Give either an email address or a mobile number")
        return self


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: str | None
    phone: str | None
    role: Role
    invited_by_name: str
    created_at: datetime
    expires_at: datetime


class InvitationLookup(BaseModel):
    """What the invite page shows before accepting (no login needed)."""

    clinic_id: uuid.UUID
    clinic_name: str
    channel: OtpChannel  # how the invitation was sent
    email: str | None
    phone: str | None
    role: Role
    invited_by_name: str
    needs_name: bool  # new user: ask for their details
    needs_password: bool  # ask them to choose a password
    needs_email: bool  # invited by phone and new: ask for an email address and verify it


class AcceptInvitationRequest(BaseModel):
    token: str
    profile: PersonDetails | None = None  # required for new users
    password: Password | None = None
    # Only for new users invited by mobile number: their email + the code emailed to it.
    email: Email | None = None
    email_code: OtpCode | None = None
