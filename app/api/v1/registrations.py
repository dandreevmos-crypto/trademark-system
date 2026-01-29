"""Registration API endpoints for managing trademark registrations."""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_current_admin_user
from app.database import get_db
from app.models import User, TrademarkRegistration, RenewalAction, Trademark, Territory
from app.models.trademark import RenewalStatus
from app.schemas.trademark import (
    RegistrationResponse,
    RegistrationUpdate,
    RenewalActionCreate,
)

router = APIRouter()


@router.get("/{registration_id}", response_model=RegistrationResponse)
async def get_registration(
    registration_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrademarkRegistration:
    """Get a single registration by ID."""
    query = (
        select(TrademarkRegistration)
        .where(TrademarkRegistration.id == registration_id)
        .options(
            selectinload(TrademarkRegistration.territory),
        )
    )

    result = await db.execute(query)
    registration = result.scalar_one_or_none()

    if not registration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registration not found",
        )

    return registration


@router.patch("/{registration_id}", response_model=RegistrationResponse)
async def update_registration(
    registration_id: UUID,
    registration_data: RegistrationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> TrademarkRegistration:
    """Update a registration (admin only)."""
    query = (
        select(TrademarkRegistration)
        .where(TrademarkRegistration.id == registration_id)
        .options(
            selectinload(TrademarkRegistration.territory),
        )
    )

    result = await db.execute(query)
    registration = result.scalar_one_or_none()

    if not registration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registration not found",
        )

    update_data = registration_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(registration, field, value)

    await db.flush()
    return registration


@router.post("/{registration_id}/renewal-filed", response_model=RegistrationResponse)
async def mark_renewal_filed(
    registration_id: UUID,
    action_data: RenewalActionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> TrademarkRegistration:
    """Mark a registration as having renewal filed."""
    query = (
        select(TrademarkRegistration)
        .where(TrademarkRegistration.id == registration_id)
        .options(
            selectinload(TrademarkRegistration.territory),
        )
    )

    result = await db.execute(query)
    registration = result.scalar_one_or_none()

    if not registration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registration not found",
        )

    # Create renewal action log
    renewal_action = RenewalAction(
        registration_id=registration_id,
        action_type="renewal_filed",
        action_date=action_data.action_date,
        previous_status=registration.renewal_status,
        new_status=RenewalStatus.RENEWAL_FILED.value,
        notes=action_data.notes,
        created_by=current_user.id,
    )
    db.add(renewal_action)

    # Update registration
    registration.renewal_status = RenewalStatus.RENEWAL_FILED.value
    registration.renewal_filed_date = action_data.action_date
    registration.renewal_notes = action_data.notes

    await db.flush()
    return registration


@router.post("/{registration_id}/not-renewing", response_model=RegistrationResponse)
async def mark_not_renewing(
    registration_id: UUID,
    action_data: RenewalActionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> TrademarkRegistration:
    """Mark a registration as decided not to renew."""
    query = (
        select(TrademarkRegistration)
        .where(TrademarkRegistration.id == registration_id)
        .options(
            selectinload(TrademarkRegistration.territory),
        )
    )

    result = await db.execute(query)
    registration = result.scalar_one_or_none()

    if not registration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registration not found",
        )

    # Create renewal action log
    renewal_action = RenewalAction(
        registration_id=registration_id,
        action_type="decided_not_renew",
        action_date=action_data.action_date,
        previous_status=registration.renewal_status,
        new_status=RenewalStatus.NOT_RENEWING.value,
        notes=action_data.notes,
        created_by=current_user.id,
    )
    db.add(renewal_action)

    # Update registration
    registration.renewal_status = RenewalStatus.NOT_RENEWING.value
    registration.renewal_decision_date = action_data.action_date
    registration.renewal_notes = action_data.notes

    await db.flush()
    return registration


@router.get("/expiring/list", response_model=List[RegistrationResponse])
async def list_expiring_registrations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    days: int = Query(180, ge=1, le=365, description="Days until expiration"),
) -> List[TrademarkRegistration]:
    """List registrations expiring within specified days."""
    from datetime import timedelta

    today = date.today()
    expiration_threshold = today + timedelta(days=days)

    query = (
        select(TrademarkRegistration)
        .where(
            TrademarkRegistration.expiration_date <= expiration_threshold,
            TrademarkRegistration.expiration_date >= today,
            TrademarkRegistration.renewal_status == RenewalStatus.ACTIVE.value,
        )
        .options(
            selectinload(TrademarkRegistration.territory),
            selectinload(TrademarkRegistration.trademark),
        )
        .order_by(TrademarkRegistration.expiration_date)
    )

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/by-territory/{territory_id}", response_model=List[RegistrationResponse])
async def list_registrations_by_territory(
    territory_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: Optional[str] = None,
) -> List[TrademarkRegistration]:
    """List all registrations for a territory."""
    query = (
        select(TrademarkRegistration)
        .where(TrademarkRegistration.territory_id == territory_id)
        .options(
            selectinload(TrademarkRegistration.territory),
            selectinload(TrademarkRegistration.trademark),
        )
    )

    if status_filter:
        query = query.where(TrademarkRegistration.status == status_filter)

    query = query.order_by(TrademarkRegistration.registration_number)

    result = await db.execute(query)
    return result.scalars().all()
