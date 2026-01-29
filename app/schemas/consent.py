"""Pydantic schemas for consent letters."""

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ConsentLetterCreate(BaseModel):
    """Schema for creating a consent letter."""

    # Правообладатель
    rights_holder_id: UUID
    signatory_name_ru: str = Field(..., min_length=1, max_length=300)
    signatory_name_en: str = Field(..., min_length=1, max_length=300)
    signatory_position_ru: str = Field(default="Директор", max_length=100)
    signatory_position_en: str = Field(default="Director", max_length=100)

    # Получатель согласия
    recipient_name_ru: str = Field(..., min_length=1, max_length=500)
    recipient_name_en: str = Field(..., min_length=1, max_length=500)
    recipient_inn: Optional[str] = Field(None, max_length=20)
    recipient_address_ru: str = Field(..., min_length=1)
    recipient_address_en: str = Field(..., min_length=1)

    # Основание (договор)
    contract_number: Optional[str] = Field(None, max_length=100)
    contract_date: Optional[date] = None

    # Цель использования
    usage_purpose_ru: str = Field(..., min_length=1)
    usage_purpose_en: str = Field(..., min_length=1)

    # Товарный знак
    trademark_name: str = Field(..., min_length=1, max_length=200)
    registration_numbers: List[str] = Field(..., min_length=1)

    # Срок действия
    valid_from: date
    valid_until: date

    # Дата документа
    document_date: date

    # Язык документа
    document_language: str = Field(default="both", pattern="^(ru|en|both)$")


class ConsentLetterUpdate(BaseModel):
    """Schema for updating a consent letter."""

    signatory_name_ru: Optional[str] = Field(None, min_length=1, max_length=300)
    signatory_name_en: Optional[str] = Field(None, min_length=1, max_length=300)
    signatory_position_ru: Optional[str] = Field(None, max_length=100)
    signatory_position_en: Optional[str] = Field(None, max_length=100)

    recipient_name_ru: Optional[str] = Field(None, min_length=1, max_length=500)
    recipient_name_en: Optional[str] = Field(None, min_length=1, max_length=500)
    recipient_inn: Optional[str] = Field(None, max_length=20)
    recipient_address_ru: Optional[str] = Field(None, min_length=1)
    recipient_address_en: Optional[str] = Field(None, min_length=1)

    contract_number: Optional[str] = Field(None, max_length=100)
    contract_date: Optional[date] = None

    usage_purpose_ru: Optional[str] = Field(None, min_length=1)
    usage_purpose_en: Optional[str] = Field(None, min_length=1)

    trademark_name: Optional[str] = Field(None, min_length=1, max_length=200)
    registration_numbers: Optional[List[str]] = None

    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    document_date: Optional[date] = None
    document_language: Optional[str] = Field(None, pattern="^(ru|en|both)$")


class RightsHolderInfo(BaseModel):
    """Minimal rights holder info for consent letters."""

    id: UUID
    name: str

    class Config:
        from_attributes = True


class ConsentLetterResponse(BaseModel):
    """Schema for consent letter response."""

    id: UUID
    rights_holder_id: UUID
    rights_holder: Optional[RightsHolderInfo] = None

    signatory_name_ru: str
    signatory_name_en: str
    signatory_position_ru: str
    signatory_position_en: str

    recipient_name_ru: str
    recipient_name_en: str
    recipient_inn: Optional[str]
    recipient_address_ru: str
    recipient_address_en: str

    contract_number: Optional[str]
    contract_date: Optional[date]

    usage_purpose_ru: str
    usage_purpose_en: str

    trademark_name: str
    registration_numbers: List[str]

    valid_from: date
    valid_until: date
    document_date: date
    document_language: str

    generated_file_path: Optional[str]

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConsentLetterListResponse(BaseModel):
    """Schema for paginated consent letters list."""

    items: List[ConsentLetterResponse]
    total: int
    page: int
    page_size: int
    pages: int
