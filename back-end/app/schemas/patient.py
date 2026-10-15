import re
import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, StringConstraints

from app.models import Gender
from app.schemas.common import Email, Name, Phone

BloodGroup = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]


def _blank_to_none(value):
    return None if isinstance(value, str) and not value.strip() else value


def _check_birth_date(value: date | None) -> date | None:
    if value is None:
        return None
    today = date.today()
    if value > today:
        raise ValueError("Date of birth can't be in the future")
    if value.year < today.year - 130:
        raise ValueError("Please check the date of birth")
    return value


def _normalize_abha(value: str | None) -> str | None:
    """ABHA numbers have 14 digits, often written 12-3456-7890-1234."""
    if value is None:
        return None
    digits = re.sub(r"[\s-]", "", value)
    if not re.fullmatch(r"\d{14}", digits):
        raise ValueError("ABHA number must have 14 digits")
    return f"{digits[:2]}-{digits[2:6]}-{digits[6:10]}-{digits[10:]}"


Optional = BeforeValidator(_blank_to_none)
BirthDate = Annotated[date | None, Optional, AfterValidator(_check_birth_date)]
AbhaNumber = Annotated[str | None, Optional, AfterValidator(_normalize_abha)]
# Length limits apply to the text only; None (left blank) is always fine.
Address = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None, Optional
]
Notes = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None, Optional
]


class PatientCreate(BaseModel):
    full_name: Name
    phone: Phone
    email: Annotated[Email | None, Optional] = None
    date_of_birth: BirthDate = None
    gender: Annotated[Gender | None, Optional] = None
    blood_group: Annotated[BloodGroup | None, Optional] = None
    address: Address = None
    abha_number: AbhaNumber = None
    notes: Notes = None  # allergies, chronic conditions…
    messaging_consent: bool = False


class PatientUpdate(BaseModel):
    """Only the fields sent are changed."""

    full_name: Name | None = None
    phone: Phone | None = None
    email: Annotated[Email | None, Optional] = None
    date_of_birth: BirthDate = None
    gender: Annotated[Gender | None, Optional] = None
    blood_group: Annotated[BloodGroup | None, Optional] = None
    address: Address = None
    abha_number: AbhaNumber = None
    notes: Notes = None
    messaging_consent: bool | None = None


class PatientOut(BaseModel):
    id: uuid.UUID
    full_name: str
    phone: str
    email: str | None
    date_of_birth: date | None
    age: int | None
    gender: Gender | None
    blood_group: str | None
    address: str | None
    abha_number: str | None
    notes: str | None
    messaging_consent: bool
    messaging_consent_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PatientPage(BaseModel):
    items: list[PatientOut]
    total: int
