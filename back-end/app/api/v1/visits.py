"""Consultations: start from an appointment, record notes and the prescription, finish (locks
the record and numbers the prescription), download the PDF, send it on WhatsApp."""

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import select

from app.api.deps import ClinicContext, ClinicCtx
from app.api.v1.patients import age_on
from app.core.config import get_settings
from app.core.database import DbSession
from app.core.security import generate_token, hash_token
from app.models import (
    Appointment,
    AppointmentStatus,
    Clinic,
    Medicine,
    Patient,
    PrescriptionItem,
    Role,
    User,
    Visit,
    VisitStatus,
)
from app.schemas.visit import (
    MedicineSuggestion,
    PrescriptionItemOut,
    ShareResult,
    VisitOut,
    VisitPatient,
    VisitSummary,
    VisitUpdate,
    Vitals,
)
from app.services.auth import utcnow
from app.services.prescriptions import (
    content_disposition,
    medicine_key,
    next_prescription_number,
    pdf_filename,
    prescription_label,
    remember_medicines,
    render_prescription_pdf,
)
from app.services.scheduling import clinic_zone
from app.services.whatsapp import (
    WhatsAppMessage,
    WhatsAppSender,
    WhatsAppTemplate,
    deliver_whatsapp,
    get_whatsapp_sender,
)

router = APIRouter(tags=["consultations"])


def _can_edit(visit: Visit, ctx: ClinicContext) -> bool:
    return visit.status == VisitStatus.IN_PROGRESS and (
        visit.doctor_id == ctx.user.id or ctx.role == Role.OWNER
    )


async def _out(db: DbSession, visit: Visit, ctx: ClinicContext) -> VisitOut:
    patient = await db.get(Patient, visit.patient_id)
    doctor = await db.get(User, visit.doctor_id)
    return VisitOut(
        id=visit.id,
        status=visit.status,
        appointment_id=visit.appointment_id,
        patient=VisitPatient(
            id=patient.id,
            full_name=patient.full_name,
            phone=patient.phone,
            age=age_on(patient.date_of_birth),
            gender=patient.gender,
            blood_group=patient.blood_group,
            notes=patient.notes,
            messaging_consent=patient.messaging_consent,
        ),
        doctor_id=doctor.id,
        doctor_name=doctor.full_name,
        vitals=Vitals(**(visit.vitals or {})),
        complaints=visit.complaints,
        examination=visit.examination,
        diagnosis=visit.diagnosis,
        advice=visit.advice,
        follow_up_date=visit.follow_up_date,
        items=[
            PrescriptionItemOut(
                medicine=i.medicine,
                dose=i.dose,
                timing=i.timing,
                duration=i.duration,
                instructions=i.instructions,
            )
            for i in visit.items
        ],
        prescription_number=prescription_label(visit),
        created_at=visit.created_at,
        completed_at=visit.completed_at,
        can_edit=_can_edit(visit, ctx),
    )


async def _get(db: DbSession, ctx: ClinicContext, visit_id: uuid.UUID) -> Visit:
    visit = await db.scalar(
        select(Visit).where(Visit.id == visit_id, Visit.clinic_id == ctx.clinic_id)
    )
    if visit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Consultation not found")
    return visit


@router.post("/appointments/{appointment_id}/consultation")
async def start_consultation(appointment_id: uuid.UUID, ctx: ClinicCtx, db: DbSession) -> VisitOut:
    """Opens the consultation for a checked-in appointment (creating it the first time)."""
    appointment = await db.scalar(
        select(Appointment).where(
            Appointment.id == appointment_id, Appointment.clinic_id == ctx.clinic_id
        )
    )
    if appointment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    visit = await db.scalar(select(Visit).where(Visit.appointment_id == appointment.id))
    if visit is None:
        if appointment.status not in (AppointmentStatus.ARRIVED, AppointmentStatus.IN_CONSULTATION):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Check the patient in before starting the consultation"
            )
        if ctx.role != Role.OWNER and ctx.user.id != appointment.doctor_id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Only the patient's doctor can start this consultation"
            )
        visit = Visit(
            clinic_id=ctx.clinic_id,
            appointment_id=appointment.id,
            patient_id=appointment.patient_id,
            doctor_id=appointment.doctor_id,
            vitals={},
        )
        db.add(visit)
        if appointment.status == AppointmentStatus.ARRIVED:
            appointment.status = AppointmentStatus.IN_CONSULTATION
            appointment.started_at = utcnow()
        await db.commit()
        await db.refresh(visit)
    return await _out(db, visit, ctx)


@router.get("/visits")
async def list_visits(ctx: ClinicCtx, db: DbSession, patient_id: uuid.UUID) -> list[VisitSummary]:
    """A patient's consultations, newest first."""
    rows = await db.execute(
        select(Visit, User)
        .join(User, User.id == Visit.doctor_id)
        .where(Visit.clinic_id == ctx.clinic_id, Visit.patient_id == patient_id)
        .order_by(Visit.created_at.desc())
        .limit(100)
    )
    return [
        VisitSummary(
            id=v.id,
            status=v.status,
            doctor_name=d.full_name,
            diagnosis=v.diagnosis,
            medicines=[i.medicine for i in v.items],
            prescription_number=prescription_label(v),
            created_at=v.created_at,
            completed_at=v.completed_at,
        )
        for v, d in rows.all()
    ]


@router.get("/visits/{visit_id}")
async def get_visit(visit_id: uuid.UUID, ctx: ClinicCtx, db: DbSession) -> VisitOut:
    return await _out(db, await _get(db, ctx, visit_id), ctx)


def _require_editable(visit: Visit, ctx: ClinicContext) -> None:
    if visit.status != VisitStatus.IN_PROGRESS:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This consultation is finished and can no longer be changed"
        )
    if not _can_edit(visit, ctx):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the patient's doctor can write this consultation"
        )


@router.patch("/visits/{visit_id}")
async def update_visit(
    visit_id: uuid.UUID, body: VisitUpdate, ctx: ClinicCtx, db: DbSession
) -> VisitOut:
    visit = await _get(db, ctx, visit_id)
    _require_editable(visit, ctx)
    changes = body.model_dump(exclude_unset=True)
    if "vitals" in changes:
        vitals = body.vitals.model_dump(exclude_none=True) if body.vitals else {}
        visit.vitals = vitals
    for field in ("complaints", "examination", "diagnosis", "advice", "follow_up_date"):
        if field in changes:
            setattr(visit, field, changes[field])
    if body.items is not None:
        visit.items = [
            PrescriptionItem(position=n, **item.model_dump())
            for n, item in enumerate(body.items, start=1)
        ]
    await db.commit()
    await db.refresh(visit)
    return await _out(db, visit, ctx)


@router.post("/visits/{visit_id}/complete")
async def complete_visit(visit_id: uuid.UUID, ctx: ClinicCtx, db: DbSession) -> VisitOut:
    """Finishes the consultation: numbers the prescription, locks the record, completes the
    appointment."""
    visit = await _get(db, ctx, visit_id)
    _require_editable(visit, ctx)
    if not (visit.diagnosis or visit.items or visit.complaints):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Add at least the complaints, a diagnosis or a medicine before finishing",
        )
    now = utcnow()
    visit.status = VisitStatus.COMPLETED
    visit.completed_at = now
    visit.prescription_number = await next_prescription_number(db, ctx.clinic_id)
    if visit.appointment_id:
        appointment = await db.get(Appointment, visit.appointment_id)
        if appointment.status in (AppointmentStatus.ARRIVED, AppointmentStatus.IN_CONSULTATION):
            appointment.status = AppointmentStatus.COMPLETED
            appointment.completed_at = now
    await remember_medicines(db, ctx.clinic_id, [i.medicine for i in visit.items])
    await db.commit()
    await db.refresh(visit)
    return await _out(db, visit, ctx)


async def _pdf_response(db: DbSession, visit: Visit, disposition: str = "inline") -> Response:
    patient = await db.get(Patient, visit.patient_id)
    doctor = await db.get(User, visit.doctor_id)
    clinic = await db.get(Clinic, visit.clinic_id)
    pdf = render_prescription_pdf(
        visit, patient, doctor, clinic, clinic_zone(clinic), age_on(patient.date_of_birth)
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": content_disposition(disposition, pdf_filename(visit, patient)),
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/visits/{visit_id}/prescription.pdf")
async def prescription_pdf(visit_id: uuid.UUID, ctx: ClinicCtx, db: DbSession) -> Response:
    """The prescription as a PDF (drafts are marked "Draft" instead of a number)."""
    return await _pdf_response(db, await _get(db, ctx, visit_id))


@router.post("/visits/{visit_id}/share")
async def share_prescription(
    visit_id: uuid.UUID,
    ctx: ClinicCtx,
    db: DbSession,
    whatsapp_sender: Annotated[WhatsAppSender, Depends(get_whatsapp_sender)],
    background: BackgroundTasks,
) -> ShareResult:
    """Sends the finished prescription to the patient on WhatsApp (needs their consent)."""
    visit = await _get(db, ctx, visit_id)
    if visit.status != VisitStatus.COMPLETED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Finish the consultation first")
    patient = await db.get(Patient, visit.patient_id)
    if not patient.messaging_consent:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "The patient hasn't agreed to WhatsApp messages. Record their consent first.",
        )
    settings = get_settings()
    token = generate_token()
    visit.share_token_hash = hash_token(token)
    visit.share_expires_at = utcnow() + timedelta(days=settings.prescription_link_days)
    await db.commit()

    doctor = await db.get(User, visit.doctor_id)
    clinic = await db.get(Clinic, visit.clinic_id)
    message = WhatsAppMessage(
        to=patient.phone,
        template=WhatsAppTemplate.PRESCRIPTION,
        params={
            "patient": patient.full_name.split()[0],
            "doctor": doctor.full_name,
            "clinic": clinic.name,
        },
        document_url=f"{settings.public_api_url}/public/prescriptions/{token}",
        document_name=pdf_filename(visit, patient),
    )
    background.add_task(deliver_whatsapp, whatsapp_sender, message)
    return ShareResult(sent_to=patient.phone, link_expires_at=visit.share_expires_at)


@router.get("/public/prescriptions/{token}", include_in_schema=False)
async def shared_prescription(token: str, db: DbSession) -> Response:
    """The link inside the WhatsApp message: no login, but unguessable and expiring."""
    visit = await db.scalar(select(Visit).where(Visit.share_token_hash == hash_token(token)))
    if visit is None or not visit.share_expires_at or visit.share_expires_at <= utcnow():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This link has expired")
    return await _pdf_response(db, visit)


@router.get("/medicines")
async def suggest_medicines(
    ctx: ClinicCtx, db: DbSession, q: Annotated[str, Query(min_length=1, max_length=100)]
) -> list[MedicineSuggestion]:
    """Medicines this clinic has prescribed before, most used first."""
    key = medicine_key(q).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = await db.scalars(
        select(Medicine)
        .where(Medicine.clinic_id == ctx.clinic_id, Medicine.name_key.like(f"%{key}%", escape="\\"))
        .order_by(Medicine.name_key.startswith(key).desc(), Medicine.times_used.desc())
        .limit(10)
    )
    return [MedicineSuggestion(name=m.name, times_used=m.times_used) for m in rows]
