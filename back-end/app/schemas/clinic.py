import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models import Role
from app.schemas.common import Name

_Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]


class ClinicFields(BaseModel):
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    address: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
    city: _Short | None = None
    state: _Short | None = None
    pincode: Annotated[str, StringConstraints(pattern=r"^\d{6}$")] | None = None
    gstin: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[0-9A-Za-z]{15}$"),
        ]
        | None
    ) = None


class ClinicCreate(ClinicFields):
    name: Name


class ClinicUpdate(ClinicFields):
    name: Name | None = None


class ClinicOut(ClinicFields):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    timezone: str


class MemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    phone: str | None
    role: Role
    is_active: bool
    joined_at: datetime


class MemberUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None
