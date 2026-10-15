import uuid
from typing import Annotated, Literal, Self

from pydantic import BaseModel, StringConstraints, TypeAdapter, model_validator

from app.models import OtpChannel, OtpPurpose, Role, Salutation
from app.schemas.common import Email, Name, Password, PersonDetails, normalize_phone

OtpCode = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{6}$")]


_EMAIL = TypeAdapter(Email)


def normalize_target(channel: OtpChannel, value: str) -> str:
    """Validates and normalises an email address or a mobile number (with country code)."""
    value = value.strip()
    if channel == OtpChannel.EMAIL:
        return _EMAIL.validate_python(value)
    return normalize_phone(value)


class Identifier(BaseModel):
    """Someone's email address or mobile number."""

    channel: OtpChannel
    target: str  # email address, or mobile number with country code (+919876543210)

    @model_validator(mode="after")
    def _normalise(self) -> Self:
        self.target = normalize_target(self.channel, self.target)
        return self


class OtpRequest(Identifier):
    purpose: OtpPurpose
    # For mobile numbers: send the code on WhatsApp or by SMS.
    delivery: Literal["whatsapp", "sms"] = "whatsapp"

    @model_validator(mode="after")
    def _allowed(self) -> Self:
        if self.purpose == OtpPurpose.REGISTER and self.channel != OtpChannel.EMAIL:
            raise ValueError("Sign-up codes are only sent by email for now")
        return self


class AuthOptions(BaseModel):
    """What the login page can offer right now."""

    phone_code_channels: list[Literal["whatsapp", "sms"]]


class OtpResponse(BaseModel):
    detail: str
    expires_in_minutes: int
    resend_after_seconds: int


class RegisterRequest(PersonDetails):
    email: Email
    email_code: OtpCode  # 6-digit code emailed by POST /auth/otp (purpose "register")
    password: Password
    clinic_name: Name


class LoginRequest(BaseModel):
    identifier: str  # email address or mobile number with country code
    password: str

    @property
    def channel(self) -> OtpChannel:
        return OtpChannel.EMAIL if "@" in self.identifier else OtpChannel.PHONE


class OtpLoginRequest(Identifier):
    code: OtpCode


class ForgotPasswordRequest(BaseModel):
    email: Email


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: Password


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    salutation: Salutation | None
    first_name: str
    middle_name: str | None
    last_name: str
    full_name: str
    phone: str | None
    email_verified: bool
    phone_verified: bool


class MembershipOut(BaseModel):
    clinic_id: uuid.UUID
    clinic_name: str
    role: Role


class MeResponse(BaseModel):
    user: UserOut
    memberships: list[MembershipOut]
