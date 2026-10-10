from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import DbSession

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: DbSession) -> dict[str, str]:
    """Reports whether the API is up and can reach the database."""
    try:
        await db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "unreachable"
    return {"status": "ok", "database": database}
