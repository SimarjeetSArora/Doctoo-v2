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
from app.models import Clinic, ClinicMember, PasswordResetToken, User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MembershipOut,
    MeResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)
from app.services.auth import (
    REFRESH_COOKIE,
    clear_refresh_cookie,
    create_clinic_with_owner,
    get_active_session,
    get_user_by_email,
    revoke_all_sessions,
    start_session,
    utcnow,
)
from app.services.email import EmailMessage, EmailSender, deliver, get_email_sender

router = APIRouter(prefix="/auth", tags=["auth"])

RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]
UserAgent = Annotated[str | None, Header()]


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest, db: DbSession, response: Response, user_agent: UserAgent = None
) -> TokenResponse:
    """Sign up a clinic owner: creates their account and their clinic."""
    if await get_user_by_email(db, body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(
        email=body.email, full_name=body.full_name, hashed_password=hash_password(body.password)
    )
    db.add(user)
    await db.flush()
    await create_clinic_with_owner(db, user, Clinic(name=body.clinic_name))
    return await start_session(db, user, response, user_agent)


@router.post("/login")
async def login(
    body: LoginRequest, db: DbSession, response: Response, user_agent: UserAgent = None
) -> TokenResponse:
    user = await get_user_by_email(db, body.email)
    password_ok = verify_password(body.password, user.hashed_password if user else None)
    if user is None or not password_ok or not user.is_active:
        # Same message either way, so attackers can't discover which emails have accounts.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
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
            full_name=user.full_name,
            phone=user.phone,
        ),
        memberships=[
            MembershipOut(clinic_id=clinic.id, clinic_name=clinic.name, role=member.role)
            for member, clinic in rows.all()
        ],
    )
