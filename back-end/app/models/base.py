import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

# Predictable constraint names, so Alembic migrations stay clean and reversible.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Every table gets: UUID primary key + created/updated timestamps (stored in UTC).
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TenantMixin:
    """Rows that belong to a single clinic. Every query on these must filter by clinic_id.

    RESTRICT: the database refuses to delete a clinic that still has records (medical data).
    """

    @declared_attr
    def clinic_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(ForeignKey("clinics.id", ondelete="RESTRICT"), index=True)


class SoftDeleteMixin:
    """Rows are never physically deleted; deleted_at marks them as removed."""

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
