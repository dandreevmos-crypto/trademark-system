"""FastAPI application entry point for Fly.io deployment."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db, Base, engine

# Use simplified API router (without sync that requires Celery)
from deploy.flyio.api_v1_flyio import api_router

STATIC_DIR = Path(__file__).parent.parent.parent / "app" / "static"


async def init_default_data():
    """Initialize default territories and admin user."""
    from sqlalchemy import select
    from app.database import async_session_maker
    from app.models import Territory, User
    from passlib.hash import bcrypt

    async with async_session_maker() as session:
        # Check if territories exist
        result = await session.execute(select(Territory).limit(1))
        if result.scalar_one_or_none() is None:
            # Add default territories
            territories = [
                Territory(code="RU", name_ru="Россия", name_en="Russia"),
                Territory(code="EU", name_ru="Европейский союз", name_en="European Union"),
                Territory(code="US", name_ru="США", name_en="United States"),
                Territory(code="CN", name_ru="Китай", name_en="China"),
                Territory(code="JP", name_ru="Япония", name_en="Japan"),
                Territory(code="KR", name_ru="Южная Корея", name_en="South Korea"),
                Territory(code="IN", name_ru="Индия", name_en="India"),
                Territory(code="BR", name_ru="Бразилия", name_en="Brazil"),
                Territory(code="GB", name_ru="Великобритания", name_en="United Kingdom"),
                Territory(code="DE", name_ru="Германия", name_en="Germany"),
                Territory(code="FR", name_ru="Франция", name_en="France"),
                Territory(code="IT", name_ru="Италия", name_en="Italy"),
                Territory(code="ES", name_ru="Испания", name_en="Spain"),
                Territory(code="CA", name_ru="Канада", name_en="Canada"),
                Territory(code="AU", name_ru="Австралия", name_en="Australia"),
                Territory(code="WIPO", name_ru="ВОИС (Мадридская система)", name_en="WIPO (Madrid System)"),
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
                hashed_password=bcrypt.hash("admin123"),
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
    # Ensure data directory exists
    os.makedirs("./data", exist_ok=True)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialize default data
    await init_default_data()

    yield
    # Shutdown
    pass


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Trademark Management System API (Fly.io Edition)",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version, "edition": "flyio"}


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
