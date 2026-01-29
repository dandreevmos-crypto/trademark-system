"""API v1 router for Render deployment (without Celery-dependent sync)."""

from fastapi import APIRouter

from app.api.v1 import auth, trademarks, registrations, reports, consents, import_data

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(trademarks.router, prefix="/trademarks", tags=["Trademarks"])
api_router.include_router(registrations.router, prefix="/registrations", tags=["Registrations"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(consents.router, prefix="/consents", tags=["Consent Letters"])
api_router.include_router(import_data.router, prefix="/import", tags=["Import Data"])

# Note: Sync router is excluded because it requires Celery
