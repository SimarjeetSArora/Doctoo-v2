import uuid

from pydantic import BaseModel

from app.models import Role
from app.schemas.common import Email, Name, Password


class RegisterRequest(BaseModel):
    full_name: Name
    email: Email
    password: Password
    clinic_name: Name


class LoginRequest(BaseModel):
    email: Email
    password: str


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
    full_name: str
    phone: str | None


class MembershipOut(BaseModel):
    clinic_id: uuid.UUID
    clinic_name: str
    role: Role


class MeResponse(BaseModel):
    user: UserOut
    memberships: list[MembershipOut]
