"""Add consent_letters table.

Revision ID: 004
Revises: 003
Create Date: 2026-01-28 18:30:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'consent_letters',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('rights_holder_id', UUID(as_uuid=True), sa.ForeignKey('rights_holders.id'), nullable=False, index=True),

        # Signatory
        sa.Column('signatory_name_ru', sa.String(300), nullable=False),
        sa.Column('signatory_name_en', sa.String(300), nullable=False),
        sa.Column('signatory_position_ru', sa.String(100), nullable=False, server_default='Директор'),
        sa.Column('signatory_position_en', sa.String(100), nullable=False, server_default='Director'),

        # Recipient
        sa.Column('recipient_name_ru', sa.String(500), nullable=False),
        sa.Column('recipient_name_en', sa.String(500), nullable=False),
        sa.Column('recipient_inn', sa.String(20), nullable=True),
        sa.Column('recipient_address_ru', sa.Text, nullable=False),
        sa.Column('recipient_address_en', sa.Text, nullable=False),

        # Contract
        sa.Column('contract_number', sa.String(100), nullable=True),
        sa.Column('contract_date', sa.Date, nullable=True),

        # Usage
        sa.Column('usage_purpose_ru', sa.Text, nullable=False),
        sa.Column('usage_purpose_en', sa.Text, nullable=False),

        # Trademark info
        sa.Column('trademark_name', sa.String(200), nullable=False),
        sa.Column('registration_numbers', JSONB, nullable=False, server_default='[]'),

        # Validity
        sa.Column('valid_from', sa.Date, nullable=False),
        sa.Column('valid_until', sa.Date, nullable=False),
        sa.Column('document_date', sa.Date, nullable=False),

        # Generated file
        sa.Column('generated_file_path', sa.String(500), nullable=True),

        # Metadata
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('consent_letters')
