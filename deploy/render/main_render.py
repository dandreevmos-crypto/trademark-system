"""FastAPI application entry point for Render deployment."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db, Base, engine

# Import individual routers (not the combined one that includes sync)
from app.api.v1 import auth, trademarks, registrations, reports, consents

STATIC_DIR = Path(__file__).parent / "static"
if not STATIC_DIR.exists():
    STATIC_DIR = Path("/app/app/static")


async def init_default_data():
    """Initialize default territories and admin user."""
    from sqlalchemy import select
    from app.database import async_session_maker
    from app.models import Territory, User
    # Pre-generated hash for "admin123" password
    ADMIN_PASSWORD_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.qVj7IkZ5yQKmGi"

    async with async_session_maker() as session:
        # Check if territories exist
        result = await session.execute(select(Territory).limit(1))
        if result.scalar_one_or_none() is None:
            # Add default territories
            territories = [
                Territory(iso_code="RU", name_ru="Россия", name_en="Russia"),
                Territory(iso_code="EU", name_ru="Европейский союз", name_en="European Union"),
                Territory(iso_code="US", name_ru="США", name_en="United States"),
                Territory(iso_code="CN", name_ru="Китай", name_en="China"),
                Territory(iso_code="JP", name_ru="Япония", name_en="Japan"),
                Territory(iso_code="KR", name_ru="Южная Корея", name_en="South Korea"),
                Territory(iso_code="IN", name_ru="Индия", name_en="India"),
                Territory(iso_code="BR", name_ru="Бразилия", name_en="Brazil"),
                Territory(iso_code="GB", name_ru="Великобритания", name_en="United Kingdom"),
                Territory(iso_code="DE", name_ru="Германия", name_en="Germany"),
                Territory(iso_code="FR", name_ru="Франция", name_en="France"),
                Territory(iso_code="IT", name_ru="Италия", name_en="Italy"),
                Territory(iso_code="ES", name_ru="Испания", name_en="Spain"),
                Territory(iso_code="CA", name_ru="Канада", name_en="Canada"),
                Territory(iso_code="AU", name_ru="Австралия", name_en="Australia"),
                Territory(iso_code="WO", name_ru="ВОИС (Мадридская система)", name_en="WIPO (Madrid System)"),
            ]
            session.add_all(territories)
            await session.commit()

        # Check if admin exists
        result = await session.execute(
            select(User).where(User.email == "admin@example.com")
        )
        if result.scalar_one_or_none() is None:
            admin = User(
                email="admin@example.com",
                hashed_password=ADMIN_PASSWORD_HASH,
                full_name="Administrator",
                role="admin",
                is_active=True,
            )
            session.add(admin)
            await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    os.makedirs("./data", exist_ok=True)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialize default data
    await init_default_data()

    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Trademark Management System API (Render Edition)",
    lifespan=lifespan,
)

# CORS middleware
cors_origins = settings.cors_origins.split(",") if "," in settings.cors_origins else [settings.cors_origins]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create API router without sync (which requires Celery)
api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(trademarks.router, prefix="/trademarks", tags=["Trademarks"])
api_router.include_router(registrations.router, prefix="/registrations", tags=["Registrations"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(consents.router, prefix="/consents", tags=["Consent Letters"])

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version, "edition": "render"}


# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    async def root():
        """Serve the main HTML page."""
        return FileResponse(STATIC_DIR / "index.html")
else:
    @app.get("/")
    async def root():
        """API root."""
        return {
            "message": "Trademark Management System API",
            "docs": "/docs",
            "health": "/health"
        }
