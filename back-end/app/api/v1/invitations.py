import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import OwnerCtx
from app.core.config import get_settings
from app.core.database import DbSession
from app.core.security import generate_token, hash_password, hash_token
from app.models import Clinic, ClinicMember, Invitation, User
from app.schemas.auth import TokenResponse
from app.schemas.invitation import (
    AcceptInvitationRequest,
    InvitationCreate,
    InvitationLookup,
    InvitationOut,
)
from app.services.auth import (
    get_user_by_email,
    revoke_all_sessions,
    start_session,
    utcnow,
)
from app.services.email import EmailMessage, EmailSender, get_email_sender

router = APIRouter(prefix="/invitations", tags=["invitations"])


def _pending():
    """SQL condition: invitation not yet accepted, revoked or expired."""
    return (
        Invitation.accepted_at.is_(None),
        Invitation.revoked_at.is_(None),
        Invitation.expires_at > utcnow(),
    )


def _out(invitation: Invitation, inviter: User) -> InvitationOut:
    return InvitationOut(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        invited_by_name=inviter.full_name,
        created_at=invitation.created_at,
        expires_at=invitation.expires_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_invitation(
    body: InvitationCreate,
    ctx: OwnerCtx,
    db: DbSession,
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> InvitationOut:
    existing_user = await get_user_by_email(db, body.email)
    if existing_user and await db.scalar(
        select(ClinicMember).where(
            ClinicMember.clinic_id == ctx.clinic_id,
            ClinicMember.user_id == existing_user.id,
            ClinicMember.is_active,
        )
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "This person is already on your team")

    # Re-inviting replaces any earlier pending invitation for the same email.
    await db.execute(
        update(Invitation)
        .where(Invitation.clinic_id == ctx.clinic_id, Invitation.email == body.email, *_pending())
        .values(revoked_at=utcnow())
    )

    settings = get_settings()
    token = generate_token()
    invitation = Invitation(
        clinic_id=ctx.clinic_id,
        email=body.email,
        role=body.role,
        token_hash=hash_token(token),
        invited_by_id=ctx.user.id,
        expires_at=utcnow() + timedelta(days=settings.invitation_expire_days),
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    clinic = await db.get(Clinic, ctx.clinic_id)
    await email_sender.send(
        EmailMessage(
            to=body.email,
            subject=f"{ctx.user.full_name} invited you to {clinic.name} on Doctoo",
            body=(
                f"{ctx.user.full_name} has invited you to join {clinic.name} as a {body.role}.\n\n"
                f"Accept the invitation (valid for {settings.invitation_expire_days} days):\n"
                f"{settings.frontend_url}/invite?token={token}"
            ),
        )
    )
    return _out(invitation, ctx.user)


@router.get("")
async def list_pending_invitations(ctx: OwnerCtx, db: DbSession) -> list[InvitationOut]:
    rows = await db.execute(
        select(Invitation, User)
        .join(User, User.id == Invitation.invited_by_id)
        .where(Invitation.clinic_id == ctx.clinic_id, *_pending())
        .order_by(Invitation.created_at.desc())
    )
    return [_out(invitation, inviter) for invitation, inviter in rows.all()]


@router.delete("/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(invitation_id: uuid.UUID, ctx: OwnerCtx, db: DbSession) -> None:
    invitation = await db.scalar(
        select(Invitation).where(
            Invitation.id == invitation_id, Invitation.clinic_id == ctx.clinic_id, *_pending()
        )
    )
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    invitation.revoked_at = utcnow()
    await db.commit()


# ---------- Public endpoints: used by the person who received the invite email ----------


async def _get_pending_invitation(db: AsyncSession, token: str) -> Invitation:
    invitation = await db.scalar(
        select(Invitation).where(Invitation.token_hash == hash_token(token), *_pending())
    )
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This invitation is invalid or has expired")
    return invitation


@router.get("/lookup")
async def lookup_invitation(token: str, db: DbSession) -> InvitationLookup:
    invitation = await _get_pending_invitation(db, token)
    clinic = await db.get(Clinic, invitation.clinic_id)
    inviter = await db.get(User, invitation.invited_by_id)
    user = await get_user_by_email(db, invitation.email)
    return InvitationLookup(
        clinic_id=clinic.id,
        clinic_name=clinic.name,
        email=invitation.email,
        role=invitation.role,
        invited_by_name=inviter.full_name,
        needs_name=user is None,
        # Existing, verified users just join. New or never-verified accounts set a password.
        needs_password=user is None or user.email_verified_at is None,
    )


@router.post("/accept")
async def accept_invitation(
    body: AcceptInvitationRequest,
    db: DbSession,
    response: Response,
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    invitation = await _get_pending_invitation(db, body.token)

    user = await get_user_by_email(db, invitation.email)
    if user is None:
        if not body.full_name or not body.password:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Name and password are required"
            )
        user = User(
            email=invitation.email,
            full_name=body.full_name,
            hashed_password=hash_password(body.password),
        )
        db.add(user)
        await db.flush()
    elif user.email_verified_at is None:
        # Clicking the emailed link proves they own this address; any password set before
        # that might not be theirs, so replace it and end other sessions.
        if not body.password:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Please choose a password")
        user.hashed_password = hash_password(body.password)
        await revoke_all_sessions(db, user.id)

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled")
    user.email_verified_at = user.email_verified_at or utcnow()

    member = await db.scalar(
        select(ClinicMember).where(
            ClinicMember.clinic_id == invitation.clinic_id, ClinicMember.user_id == user.id
        )
    )
    if member is None:
        db.add(ClinicMember(clinic_id=invitation.clinic_id, user_id=user.id, role=invitation.role))
    else:  # previously removed from this clinic: bring them back with the new role
        member.role, member.is_active = invitation.role, True
    invitation.accepted_at = utcnow()
    return await start_session(db, user, response, user_agent)
