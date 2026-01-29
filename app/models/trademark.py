"""Trademark-related models."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    Index,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RegistrationStatus(str, Enum):
    """Status of trademark registration."""

    PENDING = "pending"  # Делопроизводство, Экспертиза
    OPPOSITION = "opposition"  # Период оппозиции
    REGISTERED = "registered"  # регистрация
    PARTIAL_REGISTRATION = "partial_registration"  # частичная регистрация
    REJECTED = "rejected"  # отказ
    TERMINATED = "terminated"  # действие прекращено
    DECISION_PENDING = "decision_pending"  # Решение о регистрации


class RenewalStatus(str, Enum):
    """Status of trademark renewal."""

    ACTIVE = "active"  # Active, needs monitoring
    RENEWAL_FILED = "renewal_filed"  # Renewal application submitted
    NOT_RENEWING = "not_renewing"  # Decision not to renew
    EXPIRED = "expired"  # Already expired


class DocumentType(str, Enum):
    """Types of documents attached to trademarks."""

    CERTIFICATE = "certificate"  # Свидетельство
    APPLICATION = "application"  # Заявка
    POWER_OF_ATTORNEY = "power_of_attorney"  # Доверенность
    CORRESPONDENCE = "correspondence"  # Переписка
    OTHER = "other"


class NotificationType(str, Enum):
    """Types of notifications."""

    EXPIRATION_180 = "expiration_180"  # 6 months
    EXPIRATION_90 = "expiration_90"  # 3 months
    EXPIRATION_30 = "expiration_30"  # 1 month
    STATUS_CHANGE = "status_change"
    SYNC_FAILURE = "sync_failure"


class RightsHolder(Base):
    """Rights holder (trademark owner) entity."""

    __tablename__ = "rights_holders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    name_normalized: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )
    aliases: Mapped[List[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
    )
    contact_info: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    trademarks: Mapped[List["Trademark"]] = relationship(
        back_populates="rights_holder",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<RightsHolder {self.name[:50]}>"


class Territory(Base):
    """Country or territory for trademark registration."""

    __tablename__ = "territories"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    name_en: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    name_ru: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    iso_code: Mapped[Optional[str]] = mapped_column(
        String(3),
        nullable=True,
    )
    region: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    fee_structure: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    fips_code: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    wipo_code: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    has_individual_fee: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    registrations: Mapped[List["TrademarkRegistration"]] = relationship(
        back_populates="territory",
        lazy="selectin",
    )
    fee_schedules: Mapped[List["FeeSchedule"]] = relationship(
        back_populates="territory",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Territory {self.name_en}>"


class Trademark(Base):
    """Core trademark entity."""

    __tablename__ = "trademarks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )
    name_transliterated: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    rights_holder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rights_holders.id"),
        nullable=True,
        index=True,
    )
    image_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    image_source: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    rights_holder: Mapped[Optional["RightsHolder"]] = relationship(
        back_populates="trademarks",
        lazy="selectin",
    )
    classes: Mapped[List["TrademarkClass"]] = relationship(
        back_populates="trademark",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    registrations: Mapped[List["TrademarkRegistration"]] = relationship(
        back_populates="trademark",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    documents: Mapped[List["Document"]] = relationship(
        back_populates="trademark",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Trademark {self.name[:50]}>"


class TrademarkClass(Base):
    """ICGS (Nice Classification) class for a trademark."""

    __tablename__ = "trademark_classes"
    __table_args__ = (
        UniqueConstraint("trademark_id", "icgs_class", name="uq_trademark_class"),
        CheckConstraint("icgs_class >= 1 AND icgs_class <= 45", name="ck_icgs_class_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    trademark_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trademarks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    icgs_class: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    goods_services_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    product_group: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    # Relationships
    trademark: Mapped["Trademark"] = relationship(
        back_populates="classes",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TrademarkClass {self.icgs_class}>"


class TrademarkRegistration(Base):
    """Territory-specific trademark registration."""

    __tablename__ = "trademark_registrations"
    __table_args__ = (
        UniqueConstraint(
            "trademark_id",
            "territory_id",
            "application_number",
            name="uq_trademark_territory_application",
        ),
        Index("idx_registrations_expiration", "expiration_date"),
        Index("idx_registrations_status", "status"),
        Index("idx_registrations_renewal_status", "renewal_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    trademark_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trademarks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    territory_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("territories.id"),
        nullable=False,
        index=True,
    )

    # Application details
    filing_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    priority_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    application_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Registration details
    registration_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    registration_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    expiration_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    # Type flags
    is_national: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    is_international: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    madrid_registration_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=RegistrationStatus.PENDING.value,
    )
    status_detail: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Renewal tracking
    renewal_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=RenewalStatus.ACTIVE.value,
    )
    renewal_filed_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    renewal_decision_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    renewal_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # External sync
    fips_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    wipo_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    external_ids: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_sync_source: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    sync_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    # Metadata
    comments: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    trademark: Mapped["Trademark"] = relationship(
        back_populates="registrations",
        lazy="selectin",
    )
    territory: Mapped["Territory"] = relationship(
        back_populates="registrations",
        lazy="selectin",
    )
    renewal_actions: Mapped[List["RenewalAction"]] = relationship(
        back_populates="registration",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    documents: Mapped[List["Document"]] = relationship(
        back_populates="registration",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[List["Notification"]] = relationship(
        back_populates="registration",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    sync_logs: Mapped[List["SyncLog"]] = relationship(
        back_populates="registration",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TrademarkRegistration {self.registration_number or self.application_number}>"


class RenewalAction(Base):
    """Log of renewal-related actions."""

    __tablename__ = "renewal_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trademark_registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    action_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    previous_status: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
    )
    new_status: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    registration: Mapped["TrademarkRegistration"] = relationship(
        back_populates="renewal_actions",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<RenewalAction {self.action_type}>"


class Document(Base):
    """Document attached to trademark or registration."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "registration_id IS NOT NULL OR trademark_id IS NOT NULL",
            name="ck_document_parent",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    registration_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trademark_registrations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    trademark_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trademarks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    file_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    extra_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    registration: Mapped[Optional["TrademarkRegistration"]] = relationship(
        back_populates="documents",
        lazy="selectin",
    )
    trademark: Mapped[Optional["Trademark"]] = relationship(
        back_populates="documents",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Document {self.file_name}>"


class Notification(Base):
    """Notification record for expiration and status changes."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trademark_registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notification_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    trigger_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    scheduled_send_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    # Delivery tracking
    email_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    email_status: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    telegram_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    telegram_status: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    # Acknowledgment
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    acknowledged_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    # Suppression
    is_suppressed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    suppressed_reason: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    registration: Mapped["TrademarkRegistration"] = relationship(
        back_populates="notifications",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Notification {self.notification_type}>"


class SyncLog(Base):
    """Log of synchronization operations with FIPS/WIPO."""

    __tablename__ = "sync_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    registration_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trademark_registrations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    operation: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    changes_detected: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    raw_response: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    registration: Mapped[Optional["TrademarkRegistration"]] = relationship(
        back_populates="sync_logs",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<SyncLog {self.source} {self.status}>"


class FeeSchedule(Base):
    """Fee schedule for trademark renewals by territory."""

    __tablename__ = "fee_schedules"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    territory_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("territories.id"),
        nullable=False,
        index=True,
    )
    fee_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="CHF",
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    class_from: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    class_to: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    effective_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    effective_to: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    territory: Mapped["Territory"] = relationship(
        back_populates="fee_schedules",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<FeeSchedule {self.fee_type} {self.amount} {self.currency}>"


class ConsentLetter(Base):
    """Consent letter for trademark usage authorization."""

    __tablename__ = "consent_letters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # Правообладатель (из rights_holders)
    rights_holder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rights_holders.id"),
        nullable=False,
        index=True,
    )
    # Директор/подписант правообладателя
    signatory_name_ru: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )
    signatory_name_en: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )
    signatory_position_ru: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Директор",
    )
    signatory_position_en: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Director",
    )

    # Получатель согласия
    recipient_name_ru: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    recipient_name_en: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    recipient_inn: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    recipient_address_ru: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    recipient_address_en: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Основание (договор)
    contract_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    contract_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    # Цель использования
    usage_purpose_ru: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    usage_purpose_en: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Наименование ТЗ (общее для всех знаков в согласии)
    trademark_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    # Номера регистраций (JSON список)
    registration_numbers: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    # Срок действия
    valid_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    valid_until: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    # Дата документа
    document_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    # Язык документа: ru, en, both
    document_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="both",
    )

    # Сгенерированный файл
    generated_file_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Метаданные
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    rights_holder: Mapped["RightsHolder"] = relationship(
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ConsentLetter {self.trademark_name} -> {self.recipient_name_ru[:30]}>"


class AuditLog(Base):
    """Audit log for tracking all modifications."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    entity_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    old_values: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    new_values: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        INET,
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action}>"
