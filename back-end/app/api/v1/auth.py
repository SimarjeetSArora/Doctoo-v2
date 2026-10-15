from datetime import timedelta
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Cookie,
    Depends,
    Header,
    HTTPException,
    Response,
    status,
)
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.core.database import DbSession
from app.core.security import (
    create_access_token,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models import Clinic, ClinicMember, OtpChannel, OtpPurpose, PasswordResetToken, User
from app.schemas.auth import (
    AuthOptions,
    ForgotPasswordRequest,
    LoginRequest,
    MembershipOut,
    MeResponse,
    OtpLoginRequest,
    OtpRequest,
    OtpResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
    normalize_target,
)
from app.schemas.common import PersonDetails
from app.services.auth import (
    REFRESH_COOKIE,
    clear_refresh_cookie,
    create_clinic_with_owner,
    get_active_session,
    get_user_by_email,
    get_user_by_identifier,
    get_user_by_phone,
    mark_verified,
    revoke_all_sessions,
    start_session,
    utcnow,
)
from app.services.email import EmailMessage, EmailSender, deliver, get_email_sender
from app.services.otp import CODE_TTL, RESEND_COOLDOWN, OtpError, consume_code, issue_code
from app.services.sms import SmsMessage, SmsSender, SmsTemplate, deliver_sms, get_sms_sender
from app.services.whatsapp import (
    WhatsAppMessage,
    WhatsAppSender,
    WhatsAppTemplate,
    deliver_whatsapp,
    get_whatsapp_sender,
)

router = APIRouter(prefix="/auth", tags=["auth"])

RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]
UserAgent = Annotated[str | None, Header()]


async def _send_code(
    channel: OtpChannel,
    target: str,
    purpose: OtpPurpose,
    code: str,
    background: BackgroundTasks,
    email_sender: EmailSender,
    sms_sender: SmsSender,
    whatsapp_sender: WhatsAppSender,
    delivery: str,
) -> None:
    minutes = int(CODE_TTL.total_seconds() // 60)
    is_login = purpose == OtpPurpose.LOGIN
    action = "log in to" if is_login else "verify your email for"
    if channel == OtpChannel.EMAIL:
        message = EmailMessage(
            to=target,
            subject=f"{code} is your Doctoo {'login' if is_login else 'verification'} code",
            body=(
                f"Use this code to {action} Doctoo: {code}\n\n"
                f"It expires in {minutes} minutes. Never share this code with anyone.\n\n"
                "If you didn't ask for this, you can ignore this email."
            ),
        )
        background.add_task(deliver, email_sender, message)
    elif delivery == "whatsapp":
        message = WhatsAppMessage(
            to=target, template=WhatsAppTemplate.LOGIN_CODE, params={"code": code}
        )
        background.add_task(deliver_whatsapp, whatsapp_sender, message)
    else:
        sms = SmsMessage(
            to=target,
            template=SmsTemplate.LOGIN_CODE,
            params={"code": code, "minutes": str(minutes)},
        )
        background.add_task(deliver_sms, sms_sender, sms)


@router.get("/options")
async def auth_options() -> AuthOptions:
    """Public: which ways of receiving a login code on a phone are available right now."""
    return AuthOptions(phone_code_channels=get_settings().phone_code_channels())


@router.post("/otp")
async def send_otp(
    body: OtpRequest,
    db: DbSession,
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
    sms_sender: Annotated[SmsSender, Depends(get_sms_sender)],
    whatsapp_sender: Annotated[WhatsAppSender, Depends(get_whatsapp_sender)],
    background: BackgroundTasks,
) -> OtpResponse:
    """Sends a 6-digit code by email or SMS: to verify a new email at sign-up, or to log in."""
    if body.channel == OtpChannel.PHONE and body.delivery not in (
        available := get_settings().phone_code_channels()
    ):
        names = {"whatsapp": "WhatsApp", "sms": "SMS"}
        other = " Please use " + names[available[0]] + " instead." if available else ""
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Codes by {names[body.delivery]} aren't available yet.{other}",
        )
    user = await get_user_by_identifier(db, body.channel, body.target)
    if body.purpose == OtpPurpose.REGISTER and user is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An account with this email already exists. Please log in."
        )
    try:
        code = await issue_code(db, body.channel, body.target, body.purpose)
    except OtpError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    await db.commit()

    # Login codes are only sent to existing, active accounts, but the reply is the same either
    # way so this can't be used to find out who has an account.
    if body.purpose == OtpPurpose.REGISTER or (user is not None and user.is_active):
        await _send_code(
            body.channel,
            body.target,
            body.purpose,
            code,
            background,
            email_sender,
            sms_sender,
            whatsapp_sender,
            body.delivery,
        )
    where, how = "email", ""
    if body.channel == OtpChannel.PHONE:
        where = "mobile number"
        how = " on WhatsApp" if body.delivery == "whatsapp" else " by SMS"
    detail = (
        f"We've sent a 6-digit code to {body.target}"
        if body.purpose == OtpPurpose.REGISTER
        else f"If this {where} belongs to a Doctoo account, we've sent it a 6-digit code{how}"
    )
    return OtpResponse(
        detail=detail,
        expires_in_minutes=int(CODE_TTL.total_seconds() // 60),
        resend_after_seconds=int(RESEND_COOLDOWN.total_seconds()),
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest, db: DbSession, response: Response, user_agent: UserAgent = None
) -> TokenResponse:
    """Sign up a clinic owner: checks the emailed code, then creates their account and clinic."""
    if await get_user_by_email(db, body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    if await get_user_by_phone(db, body.phone):
        raise HTTPException(status.HTTP_409_CONFLICT, "This mobile number is already registered")
    try:
        await consume_code(db, OtpChannel.EMAIL, body.email, OtpPurpose.REGISTER, body.email_code)
    except OtpError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        email_verified_at=utcnow(),
        **body.model_dump(include=set(PersonDetails.model_fields)),
    )
    db.add(user)
    await db.flush()
    await create_clinic_with_owner(db, user, Clinic(name=body.clinic_name))
    return await start_session(db, user, response, user_agent)


@router.post("/login")
async def login(
    body: LoginRequest, db: DbSession, response: Response, user_agent: UserAgent = None
) -> TokenResponse:
    """Log in with email or mobile number (with country code) + password."""
    try:
        target = normalize_target(body.channel, body.identifier)
    except ValueError:
        target = None
    user = await get_user_by_identifier(db, body.channel, target) if target else None
    password_ok = verify_password(body.password, user.hashed_password if user else None)
    if user is None or not password_ok or not user.is_active:
        # Same message either way, so attackers can't discover which accounts exist.
        what = "email" if body.channel == OtpChannel.EMAIL else "mobile number"
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Incorrect {what} or password")
    return await start_session(db, user, response, user_agent)


@router.post("/login/otp")
async def login_with_otp(
    body: OtpLoginRequest, db: DbSession, response: Response, user_agent: UserAgent = None
) -> TokenResponse:
    """Log in with a code sent by POST /auth/otp (purpose "login") instead of a password."""
    try:
        await consume_code(db, body.channel, body.target, OtpPurpose.LOGIN, body.code)
    except OtpError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    user = await get_user_by_identifier(db, body.channel, body.target)
    if user is None or not user.is_active:
        await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect verification code")
    mark_verified(user, body.channel)  # they just received a code there
    return await start_session(db, user, response, user_agent)


@router.post("/refresh")
async def refresh(db: DbSession, response: Response, token: RefreshCookie = None) -> TokenResponse:
    """Issues a new access token using the refresh cookie."""
    session = await get_active_session(db, token)
    user = await db.get(User, session.user_id) if session else None
    if session is None or user is None or not user.is_active:
        clear_refresh_cookie(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, please log in again")
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(db: DbSession, response: Response, token: RefreshCookie = None) -> None:
    session = await get_active_session(db, token)
    if session:
        session.revoked_at = utcnow()
        await db.commit()
    clear_refresh_cookie(response)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(user: CurrentUser, db: DbSession, response: Response) -> None:
    """Logs out every device (e.g. after a lost phone or laptop)."""
    await revoke_all_sessions(db, user.id)
    await db.commit()
    clear_refresh_cookie(response)


@router.post("/password/forgot", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: DbSession,
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
    background: BackgroundTasks,
) -> dict[str, str]:
    message = {"detail": "If an account exists for that email, we've sent a reset link."}
    user = await get_user_by_email(db, body.email)
    if user is None or not user.is_active:
        return message  # same response, so this can't be used to discover accounts

    settings = get_settings()
    token = generate_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=utcnow() + timedelta(minutes=settings.password_reset_expire_minutes),
        )
    )
    await db.commit()
    link = f"{settings.frontend_url}/reset-password?token={token}"
    # Sent after the response, so the request stays fast.
    background.add_task(
        deliver,
        email_sender,
        EmailMessage(
            to=user.email,
            subject="Reset your Doctoo password",
            body=(
                f"Hi {user.full_name},\n\nReset your password using this link "
                f"(valid for {settings.password_reset_expire_minutes} minutes):\n{link}\n\n"
                "If you didn't ask for this, you can ignore this email."
            ),
        ),
    )
    return message


@router.post("/password/reset")
async def reset_password(
    body: ResetPasswordRequest, db: DbSession, response: Response, user_agent: UserAgent = None
) -> TokenResponse:
    reset = await db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(body.token))
    )
    if reset is None or reset.used_at is not None or reset.expires_at <= utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or expired")
    user = await db.get(User, reset.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or expired")

    reset.used_at = utcnow()
    user.hashed_password = hash_password(body.new_password)
    user.email_verified_at = user.email_verified_at or utcnow()  # they received our email
    await revoke_all_sessions(db, user.id)  # log out everywhere else
    return await start_session(db, user, response, user_agent)


@router.get("/me")
async def me(user: CurrentUser, db: DbSession) -> MeResponse:
    rows = await db.execute(
        select(ClinicMember, Clinic)
        .join(Clinic, Clinic.id == ClinicMember.clinic_id)
        .where(ClinicMember.user_id == user.id, ClinicMember.is_active)
        .order_by(Clinic.name)
    )
    return MeResponse(
        user=UserOut(
            id=user.id,
            email=user.email,
            salutation=user.salutation,
            first_name=user.first_name,
            middle_name=user.middle_name,
            last_name=user.last_name,
            full_name=user.full_name,
            phone=user.phone,
            email_verified=user.email_verified_at is not None,
            phone_verified=user.phone_verified_at is not None,
        ),
        memberships=[
            MembershipOut(clinic_id=clinic.id, clinic_name=clinic.name, role=member.role)
            for member, clinic in rows.all()
        ],
    )
