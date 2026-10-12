"""dock_pair_fares + ride pricing traceability

Adds the configurable fixed fare per directed origin -> destination dock pair
and two nullable columns on rides recording which pricing strategy/record
produced the persisted fare.

Revision ID: a7c3e9d41b52
Revises: 986714401e55
Create Date: 2026-10-11 12:00:00+00:00

No tariff rows are inserted: prices are business data and must be configured
explicitly (see docs/pricing-and-ride-lifecycle.md).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.types import GUID


revision: str = 'a7c3e9d41b52'
down_revision: Union[str, None] = '986714401e55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'dock_pair_fares',
        sa.Column('id', GUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('origin_dock_id', GUID(), nullable=False),
        sa.Column('destination_dock_id', GUID(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), server_default='INR', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('amount > 0', name='ck_dock_pair_fare_amount_positive'),
        sa.CheckConstraint('origin_dock_id <> destination_dock_id', name='ck_dock_pair_fare_distinct_docks'),
        sa.ForeignKeyConstraint(['origin_dock_id'], ['docks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['destination_dock_id'], ['docks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('origin_dock_id', 'destination_dock_id', name='uq_dock_pair_fare_direction'),
    )
    op.create_index(op.f('ix_dock_pair_fares_origin_dock_id'), 'dock_pair_fares', ['origin_dock_id'], unique=False)
    op.create_index(op.f('ix_dock_pair_fares_destination_dock_id'), 'dock_pair_fares', ['destination_dock_id'], unique=False)

    op.add_column('rides', sa.Column('pricing_strategy', sa.String(length=50), nullable=True))
    op.add_column('rides', sa.Column('pricing_reference_id', GUID(), nullable=True))


def downgrade() -> None:
    op.drop_column('rides', 'pricing_reference_id')
    op.drop_column('rides', 'pricing_strategy')
    op.drop_index(op.f('ix_dock_pair_fares_destination_dock_id'), table_name='dock_pair_fares')
    op.drop_index(op.f('ix_dock_pair_fares_origin_dock_id'), table_name='dock_pair_fares')
    op.drop_table('dock_pair_fares')
