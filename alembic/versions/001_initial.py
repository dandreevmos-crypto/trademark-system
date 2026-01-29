"""Initial schema with all tables.

Revision ID: 001_initial
Revises:
Create Date: 2025-01-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, default=False),
        sa.Column('telegram_id', sa.String(50), nullable=True),
        sa.Column('notification_preferences', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    # Rights holders table
    op.create_table(
        'rights_holders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('name_normalized', sa.String(500), nullable=False),
        sa.Column('aliases', postgresql.ARRAY(sa.Text), nullable=False, server_default='{}'),
        sa.Column('contact_info', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_rights_holders_name_normalized', 'rights_holders', ['name_normalized'])

    # Territories table
    op.create_table(
        'territories',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name_en', sa.String(100), nullable=False),
        sa.Column('name_ru', sa.String(100), nullable=False),
        sa.Column('iso_code', sa.String(3), nullable=True),
        sa.Column('region', sa.String(50), nullable=True),
        sa.Column('fee_structure', postgresql.JSONB(), nullable=True),
        sa.Column('fips_code', sa.String(10), nullable=True),
        sa.Column('wipo_code', sa.String(10), nullable=True),
        sa.Column('has_individual_fee', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Trademarks table
    op.create_table(
        'trademarks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('name_transliterated', sa.String(500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rights_holder_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('rights_holders.id'), nullable=True),
        sa.Column('image_path', sa.String(500), nullable=True),
        sa.Column('image_source', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_trademarks_name', 'trademarks', ['name'])
    op.create_index('ix_trademarks_rights_holder_id', 'trademarks', ['rights_holder_id'])

    # Trademark classes table
    op.create_table(
        'trademark_classes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('trademark_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('trademarks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('icgs_class', sa.Integer(), nullable=False),
        sa.Column('goods_services_description', sa.Text(), nullable=True),
        sa.Column('product_group', sa.String(100), nullable=True),
        sa.UniqueConstraint('trademark_id', 'icgs_class', name='uq_trademark_class'),
        sa.CheckConstraint('icgs_class >= 1 AND icgs_class <= 45', name='ck_icgs_class_range'),
    )
    op.create_index('ix_trademark_classes_trademark_id', 'trademark_classes', ['trademark_id'])
    op.create_index('ix_trademark_classes_icgs_class', 'trademark_classes', ['icgs_class'])
    op.create_index('ix_trademark_classes_product_group', 'trademark_classes', ['product_group'])

    # Trademark registrations table
    op.create_table(
        'trademark_registrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('trademark_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('trademarks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('territory_id', sa.Integer(), sa.ForeignKey('territories.id'), nullable=False),
        sa.Column('filing_date', sa.Date(), nullable=True),
        sa.Column('priority_date', sa.Date(), nullable=True),
        sa.Column('application_number', sa.String(100), nullable=True),
        sa.Column('registration_number', sa.String(100), nullable=True),
        sa.Column('registration_date', sa.Date(), nullable=True),
        sa.Column('expiration_date', sa.Date(), nullable=True),
        sa.Column('is_national', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_international', sa.Boolean(), nullable=False, default=False),
        sa.Column('madrid_registration_number', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('status_detail', sa.Text(), nullable=True),
        sa.Column('renewal_status', sa.String(30), nullable=False, default='active'),
        sa.Column('renewal_filed_date', sa.Date(), nullable=True),
        sa.Column('renewal_decision_date', sa.Date(), nullable=True),
        sa.Column('renewal_notes', sa.Text(), nullable=True),
        sa.Column('fips_url', sa.String(500), nullable=True),
        sa.Column('wipo_url', sa.String(500), nullable=True),
        sa.Column('external_ids', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_source', sa.String(20), nullable=True),
        sa.Column('sync_hash', sa.String(64), nullable=True),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('trademark_id', 'territory_id', 'application_number', name='uq_trademark_territory_application'),
    )
    op.create_index('ix_trademark_registrations_trademark_id', 'trademark_registrations', ['trademark_id'])
    op.create_index('ix_trademark_registrations_territory_id', 'trademark_registrations', ['territory_id'])
    op.create_index('ix_trademark_registrations_registration_number', 'trademark_registrations', ['registration_number'])
    op.create_index('idx_registrations_expiration', 'trademark_registrations', ['expiration_date'])
    op.create_index('idx_registrations_status', 'trademark_registrations', ['status'])
    op.create_index('idx_registrations_renewal_status', 'trademark_registrations', ['renewal_status'])

    # Renewal actions table
    op.create_table(
        'renewal_actions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('registration_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('trademark_registrations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_type', sa.String(30), nullable=False),
        sa.Column('action_date', sa.Date(), nullable=False),
        sa.Column('previous_status', sa.String(30), nullable=True),
        sa.Column('new_status', sa.String(30), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_renewal_actions_registration_id', 'renewal_actions', ['registration_id'])

    # Documents table
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('registration_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('trademark_registrations.id', ondelete='CASCADE'), nullable=True),
        sa.Column('trademark_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('trademarks.id', ondelete='CASCADE'), nullable=True),
        sa.Column('document_type', sa.String(50), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('extra_data', postgresql.JSONB(), nullable=True),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('registration_id IS NOT NULL OR trademark_id IS NOT NULL', name='ck_document_parent'),
    )
    op.create_index('ix_documents_registration_id', 'documents', ['registration_id'])
    op.create_index('ix_documents_trademark_id', 'documents', ['trademark_id'])
    op.create_index('ix_documents_document_type', 'documents', ['document_type'])

    # Notifications table
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('registration_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('trademark_registrations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('notification_type', sa.String(30), nullable=False),
        sa.Column('trigger_date', sa.Date(), nullable=False),
        sa.Column('scheduled_send_date', sa.Date(), nullable=False),
        sa.Column('email_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('email_status', sa.String(20), nullable=True),
        sa.Column('telegram_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('telegram_status', sa.String(20), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('is_suppressed', sa.Boolean(), nullable=False, default=False),
        sa.Column('suppressed_reason', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_notifications_registration_id', 'notifications', ['registration_id'])
    op.create_index('ix_notifications_scheduled_send_date', 'notifications', ['scheduled_send_date'])

    # Sync logs table
    op.create_table(
        'sync_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('registration_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('trademark_registrations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('operation', sa.String(30), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('changes_detected', postgresql.JSONB(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('raw_response', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_sync_logs_registration_id', 'sync_logs', ['registration_id'])
    op.create_index('ix_sync_logs_source', 'sync_logs', ['source'])
    op.create_index('ix_sync_logs_status', 'sync_logs', ['status'])
    op.create_index('ix_sync_logs_created_at', 'sync_logs', ['created_at'])

    # Fee schedules table
    op.create_table(
        'fee_schedules',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('territory_id', sa.Integer(), sa.ForeignKey('territories.id'), nullable=False),
        sa.Column('fee_type', sa.String(30), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, default='CHF'),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('class_from', sa.Integer(), nullable=True),
        sa.Column('class_to', sa.Integer(), nullable=True),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_fee_schedules_territory_id', 'fee_schedules', ['territory_id'])

    # Consent letters table
    op.create_table(
        'consent_letters',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('rights_holder_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('rights_holders.id'), nullable=False),
        sa.Column('signatory_name_ru', sa.String(300), nullable=False),
        sa.Column('signatory_name_en', sa.String(300), nullable=False),
        sa.Column('signatory_position_ru', sa.String(100), nullable=False, default='Директор'),
        sa.Column('signatory_position_en', sa.String(100), nullable=False, default='Director'),
        sa.Column('recipient_name_ru', sa.String(500), nullable=False),
        sa.Column('recipient_name_en', sa.String(500), nullable=False),
        sa.Column('recipient_inn', sa.String(20), nullable=True),
        sa.Column('recipient_address_ru', sa.Text(), nullable=False),
        sa.Column('recipient_address_en', sa.Text(), nullable=False),
        sa.Column('contract_number', sa.String(100), nullable=True),
        sa.Column('contract_date', sa.Date(), nullable=True),
        sa.Column('usage_purpose_ru', sa.Text(), nullable=False),
        sa.Column('usage_purpose_en', sa.Text(), nullable=False),
        sa.Column('trademark_name', sa.String(200), nullable=False),
        sa.Column('registration_numbers', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_until', sa.Date(), nullable=False),
        sa.Column('document_date', sa.Date(), nullable=False),
        sa.Column('document_language', sa.String(10), nullable=False, default='both'),
        sa.Column('generated_file_path', sa.String(500), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_consent_letters_rights_holder_id', 'consent_letters', ['rights_holder_id'])

    # Audit log table
    op.create_table(
        'audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('old_values', postgresql.JSONB(), nullable=True),
        sa.Column('new_values', postgresql.JSONB(), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_audit_log_user_id', 'audit_log', ['user_id'])
    op.create_index('ix_audit_log_entity_id', 'audit_log', ['entity_id'])


def downgrade() -> None:
    op.drop_table('audit_log')
    op.drop_table('consent_letters')
    op.drop_table('fee_schedules')
    op.drop_table('sync_logs')
    op.drop_table('notifications')
    op.drop_table('documents')
    op.drop_table('renewal_actions')
    op.drop_table('trademark_registrations')
    op.drop_table('trademark_classes')
    op.drop_table('trademarks')
    op.drop_table('territories')
    op.drop_table('rights_holders')
    op.drop_table('users')
