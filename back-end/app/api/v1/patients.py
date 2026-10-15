import re
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.api.deps import ClinicContext, ClinicCtx, require_roles
from app.core.database import DbSession
from app.models import Patient, Role
from app.schemas.patient import PatientCreate, PatientOut, PatientPage, PatientUpdate
from app.services.auth import utcnow

router = APIRouter(prefix="/patients", tags=["patients"])

CanArchive = Annotated[ClinicContext, Depends(require_roles(Role.OWNER, Role.DOCTOR))]


def age_on(birth: date | None, today: date | None = None) -> int | None:
    if birth is None:
        return None
    today = today or date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def to_out(patient: Patient) -> PatientOut:
    return PatientOut(
        id=patient.id,
        full_name=patient.full_name,
        phone=patient.phone,
        email=patient.email,
        date_of_birth=patient.date_of_birth,
        age=age_on(patient.date_of_birth),
        gender=patient.gender,
        blood_group=patient.blood_group,
        address=patient.address,
        abha_number=patient.abha_number,
        notes=patient.notes,
        messaging_consent=patient.messaging_consent,
        messaging_consent_at=patient.messaging_consent_at,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
    )


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("")
async def search_patients(
    ctx: ClinicCtx,
    db: DbSession,
    q: Annotated[str, Query(max_length=100)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PatientPage:
    """Newest first; `q` matches the name, or the phone number once 3+ digits are typed."""
    where = [Patient.clinic_id == ctx.clinic_id, Patient.deleted_at.is_(None)]
    q = q.strip()
    if q:
        conditions = [Patient.full_name.ilike(f"%{_escape_like(q)}%", escape="\\")]
        digits = re.sub(r"\D", "", q)
        if len(digits) >= 3:
            conditions.append(Patient.phone.like(f"%{digits}%"))
        where.append(or_(*conditions))

    total = await db.scalar(select(func.count()).select_from(Patient).where(*where))
    rows = await db.scalars(
        select(Patient)
        .where(*where)
        .order_by(Patient.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return PatientPage(items=[to_out(p) for p in rows], total=total or 0)


@router.post("", status_code=status.HTTP_201_CREATED)
async def register_patient(body: PatientCreate, ctx: ClinicCtx, db: DbSession) -> PatientOut:
    patient = Patient(clinic_id=ctx.clinic_id, **body.model_dump())
    if body.messaging_consent:
        patient.messaging_consent_at = utcnow()
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    return to_out(patient)


async def _get_patient(db: DbSession, ctx: ClinicContext, patient_id: uuid.UUID) -> Patient:
    patient = await db.scalar(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == ctx.clinic_id,
            Patient.deleted_at.is_(None),
        )
    )
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")
    return patient


@router.get("/{patient_id}")
async def get_patient(patient_id: uuid.UUID, ctx: ClinicCtx, db: DbSession) -> PatientOut:
    return to_out(await _get_patient(db, ctx, patient_id))


@router.patch("/{patient_id}")
async def update_patient(
    patient_id: uuid.UUID, body: PatientUpdate, ctx: ClinicCtx, db: DbSession
) -> PatientOut:
    patient = await _get_patient(db, ctx, patient_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("full_name", "") is None or changes.get("phone", "") is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Name and phone are required")

    # A new number or birth date means the patient app has to confirm the record again.
    if ("phone" in changes and changes["phone"] != patient.phone) or (
        "date_of_birth" in changes and changes["date_of_birth"] != patient.date_of_birth
    ):
        patient.portal_verified_at = None
    if "messaging_consent" in changes:
        consent = bool(changes.pop("messaging_consent"))
        if consent and not patient.messaging_consent:
            patient.messaging_consent_at = utcnow()
        elif not consent:
            patient.messaging_consent_at = None
        patient.messaging_consent = consent

    for field, value in changes.items():
        setattr(patient, field, value)
    await db.commit()
    await db.refresh(patient)
    return to_out(patient)


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_patient(patient_id: uuid.UUID, ctx: CanArchive, db: DbSession) -> None:
    """Hides the patient from the clinic. Medical records are kept (never hard-deleted)."""
    patient = await _get_patient(db, ctx, patient_id)
    patient.deleted_at = utcnow()
    await db.commit()
