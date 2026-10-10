from fastapi import APIRouter

from app.api.v1 import health

# All version-1 endpoints are mounted here; new feature routers get added below.
api_router = APIRouter()
api_router.include_router(health.router)
