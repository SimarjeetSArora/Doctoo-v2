import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import ClinicCtx, CurrentUser, OwnerCtx
from app.core.database import DbSession
from app.models import Clinic, ClinicMember, Role, User
from app.schemas.clinic import ClinicCreate, ClinicOut, ClinicUpdate, MemberOut, MemberUpdate
from app.services.auth import create_clinic_with_owner

router = APIRouter(prefix="/clinics", tags=["clinics"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_clinic(body: ClinicCreate, user: CurrentUser, db: DbSession) -> ClinicOut:
    """Creates another clinic owned by the current user."""
    clinic = await create_clinic_with_owner(db, user, Clinic(**body.model_dump()))
    await db.commit()
    return ClinicOut.model_validate(clinic)


@router.get("/current")
async def get_current_clinic(ctx: ClinicCtx, db: DbSession) -> ClinicOut:
    return ClinicOut.model_validate(await db.get(Clinic, ctx.clinic_id))


@router.patch("/current")
async def update_current_clinic(body: ClinicUpdate, ctx: OwnerCtx, db: DbSession) -> ClinicOut:
    clinic = await db.get(Clinic, ctx.clinic_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "name" and value is None:
            continue  # name can't be cleared
        setattr(clinic, field, value)
    await db.commit()
    return ClinicOut.model_validate(clinic)


def _member_out(member: ClinicMember, user: User) -> MemberOut:
    return MemberOut(
        id=member.id,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=member.role,
        is_active=member.is_active,
        joined_at=member.created_at,
    )


@router.get("/current/members")
async def list_members(ctx: ClinicCtx, db: DbSession) -> list[MemberOut]:
    rows = await db.execute(
        select(ClinicMember, User)
        .join(User, User.id == ClinicMember.user_id)
        .where(ClinicMember.clinic_id == ctx.clinic_id)
        .order_by(ClinicMember.is_active.desc(), User.full_name)
    )
    return [_member_out(member, user) for member, user in rows.all()]


@router.patch("/current/members/{member_id}")
async def update_member(
    member_id: uuid.UUID, body: MemberUpdate, ctx: OwnerCtx, db: DbSession
) -> MemberOut:
    """Change a team member's role, or deactivate/reactivate them."""
    member = await db.scalar(
        select(ClinicMember).where(
            ClinicMember.id == member_id, ClinicMember.clinic_id == ctx.clinic_id
        )
    )
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team member not found")

    if body.role is not None:
        member.role = body.role
    if body.is_active is not None:
        member.is_active = body.is_active

    active_owners = await db.scalar(
        select(func.count()).where(
            ClinicMember.clinic_id == ctx.clinic_id,
            ClinicMember.role == Role.OWNER,
            ClinicMember.is_active,
        )
    )
    if active_owners == 0:
        await db.rollback()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "A clinic must always have at least one active owner"
        )
    await db.commit()
    return _member_out(member, await db.get(User, member.user_id))
