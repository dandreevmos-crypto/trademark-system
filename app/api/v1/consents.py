"""Consent letters API endpoints."""

import httpx
import re
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_current_admin_user
from app.database import get_db
from app.models import User, ConsentLetter, RightsHolder
from app.schemas.consent import (
    ConsentLetterCreate,
    ConsentLetterUpdate,
    ConsentLetterResponse,
    ConsentLetterListResponse,
)
from app.services.consent_generator import generate_consent_docx, save_consent_docx

router = APIRouter()


class CompanyInfo(BaseModel):
    """Company information from INN lookup."""
    inn: str
    name: Optional[str] = None
    full_name: Optional[str] = None
    address: Optional[str] = None
    ogrn: Optional[str] = None
    kpp: Optional[str] = None
    status: Optional[str] = None
    found: bool = False


@router.get("/lookup-inn/{inn}", response_model=CompanyInfo)
async def lookup_company_by_inn(
    inn: str,
    current_user: User = Depends(get_current_user),
) -> CompanyInfo:
    """Look up company information by INN using egrul.nalog.ru."""
    # Validate INN format (10 or 12 digits)
    if not re.match(r'^\d{10}$|^\d{12}$', inn):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid INN format. Must be 10 or 12 digits.",
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Step 1: Start search on egrul.nalog.ru
            search_response = await client.post(
                "https://egrul.nalog.ru/",
                data={"query": inn},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                }
            )

            if search_response.status_code == 200:
                search_data = search_response.json()
                token = search_data.get("t")

                if token:
                    # Step 2: Wait and get results
                    import asyncio
                    await asyncio.sleep(1)

                    result_response = await client.get(
                        f"https://egrul.nalog.ru/search-result/{token}",
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "Accept": "application/json",
                        }
                    )

                    if result_response.status_code == 200:
                        result_data = result_response.json()
                        rows = result_data.get("rows", [])

                        if rows:
                            row = rows[0]
                            return CompanyInfo(
                                inn=inn,
                                name=row.get("n"),  # Short name
                                full_name=row.get("c"),  # Full name
                                address=row.get("a"),  # Address
                                ogrn=row.get("o"),  # OGRN
                                kpp=row.get("p"),  # KPP
                                status=row.get("s"),  # Status
                                found=True,
                            )

    except httpx.TimeoutException:
        pass
    except Exception as e:
        import logging
        logging.error(f"INN lookup error: {e}")

    # Return not found
    return CompanyInfo(inn=inn, found=False)


@router.get("", response_model=ConsentLetterListResponse)
async def list_consents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    rights_holder_id: Optional[UUID] = None,
    search: Optional[str] = None,
) -> ConsentLetterListResponse:
    """List consent letters with filtering and pagination."""
    query = select(ConsentLetter).options(
        selectinload(ConsentLetter.rights_holder)
    )

    if rights_holder_id:
        query = query.where(ConsentLetter.rights_holder_id == rights_holder_id)

    if search:
        query = query.where(
            (ConsentLetter.recipient_name_ru.ilike(f"%{search}%")) |
            (ConsentLetter.recipient_name_en.ilike(f"%{search}%")) |
            (ConsentLetter.trademark_name.ilike(f"%{search}%"))
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_query)
    total = result.scalar()

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(ConsentLetter.created_at.desc())

    result = await db.execute(query)
    consents = result.scalars().all()

    pages = (total + page_size - 1) // page_size

    return ConsentLetterListResponse(
        items=consents,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{consent_id}", response_model=ConsentLetterResponse)
async def get_consent(
    consent_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConsentLetter:
    """Get a single consent letter by ID."""
    query = (
        select(ConsentLetter)
        .where(ConsentLetter.id == consent_id)
        .options(selectinload(ConsentLetter.rights_holder))
    )

    result = await db.execute(query)
    consent = result.scalar_one_or_none()

    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consent letter not found",
        )

    return consent


@router.post("", response_model=ConsentLetterResponse, status_code=status.HTTP_201_CREATED)
async def create_consent(
    consent_data: ConsentLetterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConsentLetter:
    """Create a new consent letter."""
    # Validate rights holder exists
    result = await db.execute(
        select(RightsHolder).where(RightsHolder.id == consent_data.rights_holder_id)
    )
    rights_holder = result.scalar_one_or_none()
    if not rights_holder:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rights holder not found",
        )

    # Create consent letter
    consent = ConsentLetter(
        rights_holder_id=consent_data.rights_holder_id,
        signatory_name_ru=consent_data.signatory_name_ru,
        signatory_name_en=consent_data.signatory_name_en,
        signatory_position_ru=consent_data.signatory_position_ru,
        signatory_position_en=consent_data.signatory_position_en,
        recipient_name_ru=consent_data.recipient_name_ru,
        recipient_name_en=consent_data.recipient_name_en,
        recipient_inn=consent_data.recipient_inn,
        recipient_address_ru=consent_data.recipient_address_ru,
        recipient_address_en=consent_data.recipient_address_en,
        contract_number=consent_data.contract_number,
        contract_date=consent_data.contract_date,
        usage_purpose_ru=consent_data.usage_purpose_ru,
        usage_purpose_en=consent_data.usage_purpose_en,
        trademark_name=consent_data.trademark_name,
        registration_numbers=consent_data.registration_numbers,
        valid_from=consent_data.valid_from,
        valid_until=consent_data.valid_until,
        document_date=consent_data.document_date,
        document_language=consent_data.document_language,
        created_by=current_user.id,
    )

    db.add(consent)
    await db.flush()

    # Reload with relationships
    query = (
        select(ConsentLetter)
        .where(ConsentLetter.id == consent.id)
        .options(selectinload(ConsentLetter.rights_holder))
    )
    result = await db.execute(query)
    return result.scalar_one()


@router.patch("/{consent_id}", response_model=ConsentLetterResponse)
async def update_consent(
    consent_id: UUID,
    consent_data: ConsentLetterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConsentLetter:
    """Update a consent letter."""
    query = (
        select(ConsentLetter)
        .where(ConsentLetter.id == consent_id)
        .options(selectinload(ConsentLetter.rights_holder))
    )

    result = await db.execute(query)
    consent = result.scalar_one_or_none()

    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consent letter not found",
        )

    update_data = consent_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(consent, field, value)

    await db.flush()
    return consent


@router.delete("/{consent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_consent(
    consent_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> None:
    """Delete a consent letter (admin only)."""
    result = await db.execute(select(ConsentLetter).where(ConsentLetter.id == consent_id))
    consent = result.scalar_one_or_none()

    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consent letter not found",
        )

    await db.delete(consent)


@router.get("/{consent_id}/download")
async def download_consent(
    consent_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate and download consent letter as DOCX."""
    # Get consent with rights holder
    query = (
        select(ConsentLetter)
        .where(ConsentLetter.id == consent_id)
        .options(selectinload(ConsentLetter.rights_holder))
    )

    result = await db.execute(query)
    consent = result.scalar_one_or_none()

    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consent letter not found",
        )

    # Generate DOCX
    buffer = generate_consent_docx(consent, consent.rights_holder)

    # Generate filename
    recipient_short = consent.recipient_name_en.replace(' ', '_')[:30]
    date_str = consent.document_date.strftime('%d.%m.%Y')
    filename = f"Authorization_letter_for_{recipient_short}_{date_str}.docx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
