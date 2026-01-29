"""Simplified configuration for Fly.io deployment (no Redis/Celery, uses Fly Postgres)."""

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for Fly.io (PostgreSQL, no Redis)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Trademark Management System"
    app_version: str = "1.0.0"
    debug: bool = False
    secret_key: str = Field(default="change-me-in-production")

    # Database - Fly.io PostgreSQL (set via DATABASE_URL secret)
    database_url: str = Field(
        default=os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/trademarks")
    )
    database_echo: bool = False

    # JWT
    jwt_secret_key: str = Field(default="jwt-secret-change-me")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # CORS
    cors_origins: List[str] = Field(default=["*"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # Email
    smtp_host: str = Field(default="smtp.gmail.com")
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    email_from: str = Field(default="noreply@example.com")
    email_from_name: str = Field(default="Trademark System")
    smtp_use_tls: bool = True

    # Telegram
    telegram_bot_token: Optional[str] = None
    telegram_chat_ids: List[str] = Field(default=[])

    @field_validator("telegram_chat_ids", mode="before")
    @classmethod
    def parse_telegram_chat_ids(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v or []

    # External services rate limits
    fips_rate_limit_per_minute: int = 12
    wipo_rate_limit_per_minute: int = 10

    # File storage - local filesystem for Fly.io
    storage_path: str = Field(default="./data/files")

    # MinIO disabled for Fly.io (use local storage)
    minio_endpoint: str = Field(default="")
    minio_access_key: str = Field(default="")
    minio_secret_key: str = Field(default="")
    minio_bucket_name: str = Field(default="trademarks")
    minio_use_ssl: bool = False

    # Notification settings
    notification_intervals_days: List[int] = Field(default=[180, 90, 30])

    @field_validator("notification_intervals_days", mode="before")
    @classmethod
    def parse_notification_intervals(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",")]
        return v


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
