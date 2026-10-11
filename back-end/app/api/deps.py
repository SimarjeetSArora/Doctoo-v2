import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.database import DbSession
from app.core.security import decode_access_token
from app.models import ClinicMember, Role, User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """The logged-in user, from the 'Authorization: Bearer <access token>' header."""
    user_id = decode_access_token(credentials.credentials) if credentials else None
    user = await db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@dataclass
class ClinicContext:
    """Who is acting, in which clinic, with what role. Every clinic query filters by clinic_id."""

    user: User
    member: ClinicMember

    @property
    def clinic_id(self) -> uuid.UUID:
        return self.member.clinic_id

    @property
    def role(self) -> Role:
        return self.member.role


async def get_clinic_context(
    db: DbSession,
    user: CurrentUser,
    x_clinic_id: Annotated[uuid.UUID, Header(description="Clinic the request acts on")],
) -> ClinicContext:
    member = await db.scalar(
        select(ClinicMember).where(
            ClinicMember.clinic_id == x_clinic_id,
            ClinicMember.user_id == user.id,
            ClinicMember.is_active,
        )
    )
    if member is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to this clinic")
    return ClinicContext(user=user, member=member)


ClinicCtx = Annotated[ClinicContext, Depends(get_clinic_context)]


def require_roles(*roles: Role) -> Callable[[ClinicContext], Awaitable[ClinicContext]]:
    """Dependency factory: allow only members with one of these roles."""

    async def checker(ctx: ClinicCtx) -> ClinicContext:
        if ctx.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role can't do this")
        return ctx

    return checker


OwnerCtx = Annotated[ClinicContext, Depends(require_roles(Role.OWNER))]
