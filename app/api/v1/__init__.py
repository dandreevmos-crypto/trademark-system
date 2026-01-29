"""API v1 router."""

from fastapi import APIRouter

from app.api.v1 import auth, trademarks, registrations, reports, sync, consents

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(trademarks.router, prefix="/trademarks", tags=["Trademarks"])
api_router.include_router(registrations.router, prefix="/registrations", tags=["Registrations"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(sync.router, prefix="/sync", tags=["Synchronization"])
api_router.include_router(consents.router, prefix="/consents", tags=["Consent Letters"])
