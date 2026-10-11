from fastapi import APIRouter

from app.api.v1 import auth, clinics, health, invitations

# All version-1 endpoints are mounted here; new feature routers get added below.
api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(clinics.router)
api_router.include_router(invitations.router)
