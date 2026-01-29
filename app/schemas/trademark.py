"""Trademark-related Pydantic schemas."""

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ClassResponse(BaseModel):
    """ICGS class response schema."""

    id: UUID
    icgs_class: int
    goods_services_description: Optional[str] = None
    product_group: Optional[str] = None

    class Config:
        from_attributes = True


class TerritoryResponse(BaseModel):
    """Territory response schema."""

    id: int
    name_en: str
    name_ru: str
    iso_code: Optional[str] = None
    region: Optional[str] = None

    class Config:
        from_attributes = True


class RightsHolderResponse(BaseModel):
    """Rights holder response schema."""

    id: UUID
    name: str
    aliases: List[str] = []

    class Config:
        from_attributes = True


class RegistrationBase(BaseModel):
    """Base registration schema."""

    territory_id: int
    filing_date: Optional[date] = None
    priority_date: Optional[date] = None
    expiration_date: Optional[date] = None
    application_number: Optional[str] = None
    registration_number: Optional[str] = None
    is_national: bool = False
    is_international: bool = False
    madrid_registration_number: Optional[str] = None
    comments: Optional[str] = None


class RegistrationCreate(RegistrationBase):
    """Schema for creating a registration."""

    pass


class RegistrationUpdate(BaseModel):
    """Schema for updating a registration."""

    expiration_date: Optional[date] = None
    status: Optional[str] = None
    renewal_status: Optional[str] = None
    renewal_filed_date: Optional[date] = None
    renewal_notes: Optional[str] = None
    comments: Optional[str] = None


class RegistrationResponse(RegistrationBase):
    """Registration response schema."""

    id: UUID
    trademark_id: UUID
    status: str
    status_detail: Optional[str] = None
    renewal_status: str
    renewal_filed_date: Optional[date] = None
    renewal_decision_date: Optional[date] = None
    renewal_notes: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    last_sync_source: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    territory: TerritoryResponse

    class Config:
        from_attributes = True


class TrademarkBase(BaseModel):
    """Base trademark schema."""

    name: str = Field(min_length=1, max_length=500)
    description: Optional[str] = None
    rights_holder_id: Optional[UUID] = None


class TrademarkCreate(TrademarkBase):
    """Schema for creating a trademark."""

    classes: List[int] = Field(default=[], description="List of ICGS class numbers (1-45)")
    registrations: List[RegistrationCreate] = []


class TrademarkUpdate(BaseModel):
    """Schema for updating a trademark."""

    name: Optional[str] = None
    description: Optional[str] = None
    rights_holder_id: Optional[UUID] = None


class TrademarkResponse(TrademarkBase):
    """Trademark response schema."""

    id: UUID
    name_transliterated: Optional[str] = None
    image_path: Optional[str] = None
    image_source: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    rights_holder: Optional[RightsHolderResponse] = None
    classes: List[ClassResponse] = []
    registrations: List[RegistrationResponse] = []

    class Config:
        from_attributes = True


class TrademarkListResponse(BaseModel):
    """Paginated trademark list response."""

    items: List[TrademarkResponse]
    total: int
    page: int
    page_size: int
    pages: int


class RenewalActionCreate(BaseModel):
    """Schema for creating a renewal action."""

    action_type: str = Field(
        description="Type: 'renewal_filed', 'decided_not_renew', 'status_changed'"
    )
    action_date: date
    notes: Optional[str] = None


class TrademarkExportFilters(BaseModel):
    """Filters for trademark export."""

    rights_holder_ids: Optional[List[UUID]] = None
    territory_ids: Optional[List[int]] = None
    icgs_classes: Optional[List[int]] = None
    product_groups: Optional[List[str]] = None
    statuses: Optional[List[str]] = None
    renewal_statuses: Optional[List[str]] = None
    expiration_from: Optional[date] = None
    expiration_to: Optional[date] = None
    include_expired: bool = False
    include_rejected: bool = False


class SyncStatusResponse(BaseModel):
    """Sync status response."""

    registration_id: UUID
    source: str
    status: str
    last_sync_at: Optional[datetime] = None
    changes_detected: Optional[dict] = None
    error_message: Optional[str] = None
