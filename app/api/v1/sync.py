"""Sync API endpoints for triggering synchronization with FIPS and WIPO."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_admin_user
from app.database import get_db
from app.models import User, SyncLog, TrademarkRegistration
from app.tasks.sync_tasks import (
    sync_fips_trademarks,
    sync_wipo_trademarks,
    sync_single_registration,
    sync_priority_registrations,
)

router = APIRouter()


class SyncResponse(BaseModel):
    """Response for sync trigger."""
    message: str
    task_id: Optional[str] = None


class SyncStats(BaseModel):
    """Sync statistics."""
    total_syncs: int
    successful_syncs: int
    failed_syncs: int
    fips_syncs: int
    wipo_syncs: int
    last_sync_at: Optional[str] = None


class SyncLogResponse(BaseModel):
    """Sync log entry."""
    id: str
    registration_id: Optional[str]
    source: str
    operation: str
    status: str
    changes_detected: Optional[dict]
    error_message: Optional[str]
    duration_ms: Optional[int]
    created_at: str


@router.post("/fips", response_model=SyncResponse)
async def trigger_fips_sync(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_admin_user),
) -> SyncResponse:
    """
    Trigger FIPS synchronization for Russian trademarks.

    Requires admin privileges.
    Rate limited to 12 requests per minute to FIPS.
    """
    task = sync_fips_trademarks.delay(limit=limit)
    return SyncResponse(
        message=f"FIPS sync started for up to {limit} registrations",
        task_id=task.id
    )


@router.post("/wipo", response_model=SyncResponse)
async def trigger_wipo_sync(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_admin_user),
) -> SyncResponse:
    """
    Trigger WIPO synchronization for international trademarks.

    Requires admin privileges.
    Rate limited to 10 requests per minute to WIPO.
    """
    task = sync_wipo_trademarks.delay(limit=limit)
    return SyncResponse(
        message=f"WIPO sync started for up to {limit} registrations",
        task_id=task.id
    )


@router.post("/priority", response_model=SyncResponse)
async def trigger_priority_sync(
    current_user: User = Depends(get_current_admin_user),
) -> SyncResponse:
    """
    Trigger priority sync for registrations expiring within 6 months.

    Syncs both FIPS and WIPO sources for priority registrations.
    Requires admin privileges.
    """
    task = sync_priority_registrations.delay()
    return SyncResponse(
        message="Priority sync started for expiring registrations",
        task_id=task.id
    )


@router.post("/registration/{registration_id}", response_model=SyncResponse)
async def trigger_single_sync(
    registration_id: UUID,
    source: str = Query(..., regex="^(fips|wipo)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> SyncResponse:
    """
    Trigger sync for a single registration.

    Args:
        registration_id: The registration to sync
        source: Data source ('fips' or 'wipo')

    Requires admin privileges.
    """
    # Verify registration exists
    query = select(TrademarkRegistration).where(
        TrademarkRegistration.id == registration_id
    )
    result = await db.execute(query)
    registration = result.scalar_one_or_none()

    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    task = sync_single_registration.delay(str(registration_id), source)
    return SyncResponse(
        message=f"Sync started for registration {registration_id} from {source}",
        task_id=task.id
    )


@router.get("/stats", response_model=SyncStats)
async def get_sync_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SyncStats:
    """Get synchronization statistics."""
    # Total syncs
    total_query = select(func.count(SyncLog.id))
    total_result = await db.execute(total_query)
    total = total_result.scalar() or 0

    # Successful syncs
    success_query = select(func.count(SyncLog.id)).where(SyncLog.status == "success")
    success_result = await db.execute(success_query)
    successful = success_result.scalar() or 0

    # Failed syncs
    failed_query = select(func.count(SyncLog.id)).where(SyncLog.status == "failed")
    failed_result = await db.execute(failed_query)
    failed = failed_result.scalar() or 0

    # FIPS syncs
    fips_query = select(func.count(SyncLog.id)).where(SyncLog.source == "fips")
    fips_result = await db.execute(fips_query)
    fips = fips_result.scalar() or 0

    # WIPO syncs
    wipo_query = select(func.count(SyncLog.id)).where(SyncLog.source == "wipo")
    wipo_result = await db.execute(wipo_query)
    wipo = wipo_result.scalar() or 0

    # Last sync
    last_query = select(SyncLog.created_at).order_by(SyncLog.created_at.desc()).limit(1)
    last_result = await db.execute(last_query)
    last_sync = last_result.scalar()

    return SyncStats(
        total_syncs=total,
        successful_syncs=successful,
        failed_syncs=failed,
        fips_syncs=fips,
        wipo_syncs=wipo,
        last_sync_at=last_sync.isoformat() if last_sync else None,
    )


@router.get("/logs", response_model=list[SyncLogResponse])
async def get_sync_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    source: Optional[str] = Query(None, regex="^(fips|wipo|system)$"),
    status: Optional[str] = Query(None, regex="^(success|failed|completed)$"),
    registration_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SyncLogResponse]:
    """Get sync operation logs."""
    query = select(SyncLog).order_by(SyncLog.created_at.desc())

    if source:
        query = query.where(SyncLog.source == source)
    if status:
        query = query.where(SyncLog.status == status)
    if registration_id:
        query = query.where(SyncLog.registration_id == registration_id)

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        SyncLogResponse(
            id=str(log.id),
            registration_id=str(log.registration_id) if log.registration_id else None,
            source=log.source,
            operation=log.operation,
            status=log.status,
            changes_detected=log.changes_detected,
            error_message=log.error_message,
            duration_ms=log.duration_ms,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]
