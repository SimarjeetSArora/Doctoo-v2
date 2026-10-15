"""The patient app: patients log in with a code sent to the mobile number their clinic recorded,
then see their own clinics, doctors, prescriptions and reports."""

import uuid
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
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.api.v1.patients import age_on
from app.core.config import get_settings
from app.core.database import DbSession
from app.core.security import create_access_token, decode_access_token
from app.models import (
    Clinic,
    ClinicMember,
    OtpChannel,
    OtpPurpose,
    PatientAccount,
    Role,
    Salutation,
    User,
)
from app.schemas.auth import OtpResponse, TokenResponse
from app.schemas.patient_portal import (
    ClinicCard,
    DoctorCard,
    PatientLoginRequest,
    PatientMe,
    PatientOtpRequest,
    ProfileDetails,
    ProfileSummary,
    VerifyProfileRequest,
)
from app.services.auth import utcnow
from app.services.otp import CODE_TTL, RESEND_COOLDOWN, OtpError, consume_code, issue_code
from app.services.patient_portal import (
    DOB_LOCK,
    DOB_MAX_ATTEMPTS,
    PATIENT_REFRESH_COOKIE,
    PATIENT_TOKEN_TYPE,
    Profile,
    clear_patient_cookie,
    get_active_patient_session,
    profiles_for_phone,
    records_for_phone,
    start_patient_session,
)
from app.services.sms import SmsMessage, SmsSender, SmsTemplate, deliver_sms, get_sms_sender
from app.services.whatsapp import (
    WhatsAppMessage,
    WhatsAppSender,
    WhatsAppTemplate,
    deliver_whatsapp,
    get_whatsapp_sender,
)

router = APIRouter(prefix="/patient", tags=["patient app"])

_bearer = HTTPBearer(auto_error=False)
UserAgent = Annotated[str | None, Header()]


async def get_patient_account(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> PatientAccount:
    account_id = (
        decode_access_token(credentials.credentials, PATIENT_TOKEN_TYPE) if credentials else None
    )
    account = await db.get(PatientAccount, account_id) if account_id else None
    if account is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Not logged in", headers={"WWW-Authenticate": "Bearer"}
        )
    return account


CurrentPatient = Annotated[PatientAccount, Depends(get_patient_account)]


# ---------- Login ----------


@router.post("/auth/otp")
async def send_patient_code(
    body: PatientOtpRequest,
    db: DbSession,
    sms_sender: Annotated[SmsSender, Depends(get_sms_sender)],
    whatsapp_sender: Annotated[WhatsAppSender, Depends(get_whatsapp_sender)],
    background: BackgroundTasks,
) -> OtpResponse:
    if body.delivery not in get_settings().phone_code_channels():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "This way of sending codes isn't available"
        )
    try:
        code = await issue_code(db, OtpChannel.PHONE, body.phone, OtpPurpose.PATIENT_LOGIN)
    except OtpError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    await db.commit()

    # Only numbers a clinic has registered get a code; the reply is the same either way.
    if await records_for_phone(db, body.phone):
        if body.delivery == "whatsapp":
            message = WhatsAppMessage(
                to=body.phone, template=WhatsAppTemplate.LOGIN_CODE, params={"code": code}
            )
            background.add_task(deliver_whatsapp, whatsapp_sender, message)
        else:
            minutes = str(int(CODE_TTL.total_seconds() // 60))
            sms = SmsMessage(
                to=body.phone,
                template=SmsTemplate.LOGIN_CODE,
                params={"code": code, "minutes": minutes},
            )
            background.add_task(deliver_sms, sms_sender, sms)
    how = "on WhatsApp" if body.delivery == "whatsapp" else "by SMS"
    return OtpResponse(
        detail=f"If a clinic on Doctoo has registered this number, we've sent a code {how}",
        expires_in_minutes=int(CODE_TTL.total_seconds() // 60),
        resend_after_seconds=int(RESEND_COOLDOWN.total_seconds()),
    )


@router.post("/auth/login")
async def patient_login(
    body: PatientLoginRequest, db: DbSession, response: Response, user_agent: UserAgent = None
) -> TokenResponse:
    try:
        await consume_code(db, OtpChannel.PHONE, body.phone, OtpPurpose.PATIENT_LOGIN, body.code)
    except OtpError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    if not await records_for_phone(db, body.phone):
        await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect verification code")

    account = await db.scalar(select(PatientAccount).where(PatientAccount.phone == body.phone))
    if account is None:
        account = PatientAccount(phone=body.phone)
        db.add(account)
        await db.flush()
    account.last_login_at = utcnow()
    return await start_patient_session(db, account, response, user_agent)


@router.post("/auth/refresh")
async def patient_refresh(
    db: DbSession,
    response: Response,
    token: Annotated[str | None, Cookie(alias=PATIENT_REFRESH_COOKIE)] = None,
) -> TokenResponse:
    session = await get_active_patient_session(db, token)
    if session is None:
        clear_patient_cookie(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, please log in again")
    return TokenResponse(access_token=create_access_token(session.account_id, PATIENT_TOKEN_TYPE))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def patient_logout(
    db: DbSession,
    response: Response,
    token: Annotated[str | None, Cookie(alias=PATIENT_REFRESH_COOKIE)] = None,
) -> None:
    session = await get_active_patient_session(db, token)
    if session:
        session.revoked_at = utcnow()
        await db.commit()
    clear_patient_cookie(response)


# ---------- Profiles ----------


@router.get("/me")
async def patient_me(account: CurrentPatient, db: DbSession) -> PatientMe:
    profiles = await profiles_for_phone(db, account.phone)
    return PatientMe(
        phone=account.phone,
        profiles=[
            ProfileSummary(
                id=p.id,
                name=p.full_name if p.verified else p.masked_name,
                verified=p.verified,
                can_verify=p.date_of_birth is not None,
                clinic_count=len({r.clinic_id for r in p.records}),
            )
            for p in profiles
        ],
    )


async def _get_profile(db: DbSession, account: PatientAccount, profile_id: uuid.UUID) -> Profile:
    for profile in await profiles_for_phone(db, account.phone):
        if profile.id == profile_id:
            return profile
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")


@router.post("/profiles/{profile_id}/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify_profile(
    profile_id: uuid.UUID, body: VerifyProfileRequest, account: CurrentPatient, db: DbSession
) -> None:
    """Confirms a profile with its date of birth (protects against a mistyped number)."""
    profile = await _get_profile(db, account, profile_id)
    if profile.verified:
        return
    if profile.date_of_birth is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Your clinic hasn't recorded your date of birth yet. Please ask them to add it.",
        )
    now = utcnow()
    if account.dob_locked_until and account.dob_locked_until > now:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many wrong attempts. Please try again later."
        )

    if body.date_of_birth != profile.date_of_birth:
        account.dob_failed_attempts += 1
        left = DOB_MAX_ATTEMPTS - account.dob_failed_attempts
        if left <= 0:
            account.dob_failed_attempts = 0
            account.dob_locked_until = now + DOB_LOCK
            await db.commit()
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many wrong attempts. Please try again in an hour.",
            )
        await db.commit()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"That date of birth doesn't match. {left} attempt{'s' if left != 1 else ''} left.",
        )

    account.dob_failed_attempts = 0
    for record in profile.records:
        record.portal_verified_at = now
    await db.commit()


@router.get("/profiles/{profile_id}")
async def profile_details(
    profile_id: uuid.UUID, account: CurrentPatient, db: DbSession
) -> ProfileDetails:
    profile = await _get_profile(db, account, profile_id)
    if not profile.verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Please confirm your date of birth first")
    # A new clinic registration of the same person (same name + birth date) joins the profile.
    now = utcnow()
    for record in profile.records:
        record.portal_verified_at = record.portal_verified_at or now
    await db.commit()

    clinic_ids = list(dict.fromkeys(r.clinic_id for r in profile.records))
    since = {}
    for record in profile.records:
        since.setdefault(record.clinic_id, record.created_at.date())
    clinics = {c.id: c for c in await db.scalars(select(Clinic).where(Clinic.id.in_(clinic_ids)))}

    # Doctors at the patient's clinics (doctor role, or an owner who is a doctor).
    rows = await db.execute(
        select(ClinicMember, User)
        .join(User, User.id == ClinicMember.user_id)
        .where(ClinicMember.clinic_id.in_(clinic_ids), ClinicMember.is_active, User.is_active)
        .order_by(User.first_name)
    )
    doctors = [
        DoctorCard(
            name=user.full_name,
            clinic_id=member.clinic_id,
            clinic_name=clinics[member.clinic_id].name,
        )
        for member, user in rows.all()
        if member.role == Role.DOCTOR
        or (member.role == Role.OWNER and user.salutation == Salutation.DR)
    ]

    latest = profile.records[-1]
    return ProfileDetails(
        id=profile.id,
        full_name=profile.full_name,
        date_of_birth=profile.date_of_birth,
        age=age_on(profile.date_of_birth),
        gender=latest.gender,
        blood_group=latest.blood_group,
        clinics=[
            ClinicCard(
                id=clinics[cid].id,
                name=clinics[cid].name,
                phone=clinics[cid].phone,
                email=clinics[cid].email,
                address=clinics[cid].address,
                city=clinics[cid].city,
                state=clinics[cid].state,
                pincode=clinics[cid].pincode,
                patient_since=since[cid],
            )
            for cid in clinic_ids
        ],
        doctors=doctors,
        prescriptions=[],
        reports=[],
    )
