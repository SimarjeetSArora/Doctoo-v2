import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import OwnerCtx
from app.core.config import get_settings
from app.core.database import DbSession
from app.core.security import generate_token, hash_password, hash_token
from app.models import Clinic, ClinicMember, Invitation, OtpChannel, OtpPurpose, User
from app.schemas.auth import TokenResponse
from app.schemas.invitation import (
    AcceptInvitationRequest,
    InvitationCreate,
    InvitationLookup,
    InvitationOut,
)
from app.services.auth import (
    get_user_by_email,
    get_user_by_identifier,
    get_user_by_phone,
    mark_verified,
    revoke_all_sessions,
    start_session,
    utcnow,
)
from app.services.email import EmailMessage, EmailSender, deliver, get_email_sender
from app.services.otp import OtpError, consume_code
from app.services.sms import SmsMessage, SmsSender, SmsTemplate, deliver_sms, get_sms_sender
from app.services.whatsapp import (
    WhatsAppMessage,
    WhatsAppSender,
    WhatsAppTemplate,
    deliver_whatsapp,
    get_whatsapp_sender,
)

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
        phone=invitation.phone,
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
    sms_sender: Annotated[SmsSender, Depends(get_sms_sender)],
    whatsapp_sender: Annotated[WhatsAppSender, Depends(get_whatsapp_sender)],
    background: BackgroundTasks,
) -> InvitationOut:
    channel = OtpChannel.EMAIL if body.email else OtpChannel.PHONE
    target = body.email or body.phone
    existing_user = await get_user_by_identifier(db, channel, target)
    if existing_user and await db.scalar(
        select(ClinicMember).where(
            ClinicMember.clinic_id == ctx.clinic_id,
            ClinicMember.user_id == existing_user.id,
            ClinicMember.is_active,
        )
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "This person is already on your team")

    # Re-inviting replaces any earlier pending invitation to the same email / number.
    same_contact = Invitation.email == body.email if body.email else Invitation.phone == body.phone
    await db.execute(
        update(Invitation)
        .where(Invitation.clinic_id == ctx.clinic_id, same_contact, *_pending())
        .values(revoked_at=utcnow())
    )

    settings = get_settings()
    token = generate_token()
    invitation = Invitation(
        clinic_id=ctx.clinic_id,
        email=body.email,
        phone=body.phone,
        role=body.role,
        token_hash=hash_token(token),
        invited_by_id=ctx.user.id,
        expires_at=utcnow() + timedelta(days=settings.invitation_expire_days),
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    clinic = await db.get(Clinic, ctx.clinic_id)
    link = f"{settings.frontend_url}/invite?token={token}"
    # Sent after the response, so the request stays fast.
    if channel == OtpChannel.EMAIL:
        message = EmailMessage(
            to=body.email,
            subject=f"{ctx.user.full_name} invited you to {clinic.name} on Doctoo",
            body=(
                f"{ctx.user.full_name} has invited you to join {clinic.name} as a {body.role}.\n\n"
                f"Accept the invitation (valid for {settings.invitation_expire_days} days):\n"
                f"{link}"
            ),
        )
        background.add_task(deliver, email_sender, message)
    else:
        params = {
            "inviter": ctx.user.full_name,
            "clinic": clinic.name,
            "role": body.role,
            "days": str(settings.invitation_expire_days),
            "link": link,
        }
        if settings.phone_invite_via == "whatsapp":
            message = WhatsAppMessage(
                to=body.phone, template=WhatsAppTemplate.INVITATION, params=params
            )
            background.add_task(deliver_whatsapp, whatsapp_sender, message)
        else:
            sms = SmsMessage(to=body.phone, template=SmsTemplate.INVITATION, params=params)
            background.add_task(deliver_sms, sms_sender, sms)
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


# ---------- Public endpoints: used by the person who received the invitation ----------


async def _get_pending_invitation(db: AsyncSession, token: str) -> Invitation:
    invitation = await db.scalar(
        select(Invitation).where(Invitation.token_hash == hash_token(token), *_pending())
    )
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This invitation is invalid or has expired")
    return invitation


def _channel(invitation: Invitation) -> OtpChannel:
    return OtpChannel.EMAIL if invitation.email else OtpChannel.PHONE


async def _invited_user(db: AsyncSession, invitation: Invitation) -> User | None:
    """The existing account the invitation is for, if any."""
    user = await get_user_by_identifier(db, _channel(invitation), invitation.sent_to)
    if user is not None and _channel(invitation) == OtpChannel.PHONE and not user.phone_verified_at:
        # Anyone can type any number at sign-up. Joining a clinic through this account could hand
        # the clinic's access to whoever registered it, not the number's real owner.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This mobile number belongs to a Doctoo account that hasn't verified it yet. "
            "Please ask the clinic owner to invite you by email instead.",
        )
    return user


@router.get("/lookup")
async def lookup_invitation(token: str, db: DbSession) -> InvitationLookup:
    invitation = await _get_pending_invitation(db, token)
    clinic = await db.get(Clinic, invitation.clinic_id)
    inviter = await db.get(User, invitation.invited_by_id)
    user = await _invited_user(db, invitation)
    by_phone = _channel(invitation) == OtpChannel.PHONE
    return InvitationLookup(
        clinic_id=clinic.id,
        clinic_name=clinic.name,
        channel=_channel(invitation),
        email=invitation.email,
        phone=invitation.phone,
        role=invitation.role,
        invited_by_name=inviter.full_name,
        needs_name=user is None,
        # Existing, verified users just join. New or never-verified accounts set a password.
        needs_password=user is None or (not by_phone and user.email_verified_at is None),
        needs_email=user is None and by_phone,
    )


@router.post("/accept")
async def accept_invitation(
    body: AcceptInvitationRequest,
    db: DbSession,
    response: Response,
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    invitation = await _get_pending_invitation(db, body.token)
    channel = _channel(invitation)
    user = await _invited_user(db, invitation)

    if user is None:
        if body.profile is None or not body.password:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Your details and a password are required"
            )
        profile = body.profile.model_dump()
        if channel == OtpChannel.EMAIL:
            email = invitation.email
        else:
            # Invited by mobile: that number is theirs; they also need a verified email.
            profile["phone"] = invitation.phone
            if not body.email or not body.email_code:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "Please add your email address and the code we sent to it",
                )
            if await get_user_by_email(db, body.email):
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "An account with this email already exists. "
                    "Ask the clinic owner to invite that email instead.",
                )
            try:
                await consume_code(
                    db, OtpChannel.EMAIL, body.email, OtpPurpose.REGISTER, body.email_code
                )
            except OtpError as exc:
                raise HTTPException(exc.status_code, exc.message) from exc
            email = body.email
        if await get_user_by_phone(db, profile["phone"]):
            raise HTTPException(
                status.HTTP_409_CONFLICT, "This mobile number is already registered"
            )

        user = User(
            email=email,
            hashed_password=hash_password(body.password),
            email_verified_at=utcnow(),  # proven by the invite link or the emailed code
            **profile,
        )
        db.add(user)
        await db.flush()
    elif channel == OtpChannel.EMAIL and user.email_verified_at is None:
        # Clicking the emailed link proves they own this address; any password set before
        # that might not be theirs, so replace it and end other sessions.
        if not body.password:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Please choose a password")
        user.hashed_password = hash_password(body.password)
        await revoke_all_sessions(db, user.id)

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled")
    mark_verified(user, channel)  # the invitation link reached them there

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
