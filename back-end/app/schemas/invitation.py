import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models import Role
from app.schemas.common import Email, Name, Password


class InvitationCreate(BaseModel):
    email: Email
    role: Role


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: str
    role: Role
    invited_by_name: str
    created_at: datetime
    expires_at: datetime


class InvitationLookup(BaseModel):
    """What the invite page shows before accepting (no login needed)."""

    clinic_id: uuid.UUID
    clinic_name: str
    email: str
    role: Role
    invited_by_name: str
    needs_name: bool  # new user: ask for their name
    needs_password: bool  # ask them to choose a password


class AcceptInvitationRequest(BaseModel):
    token: str
    full_name: Name | None = None
    password: Password | None = None
