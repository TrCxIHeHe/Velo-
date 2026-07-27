"""security_hardening: fcm_token, wallet amount CHECK constraint

Revision ID: a1b2c3d4e5f6
Revises: c43cb8108df7
Create Date: 2026-07-28 00:00:00.000000+00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'c43cb8108df7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('fcm_token', sa.String(length=255), nullable=True))
    op.create_check_constraint(
        'ck_wallet_txn_amount_positive', 'wallet_transactions', 'amount > 0'
    )


def downgrade() -> None:
    op.drop_constraint('ck_wallet_txn_amount_positive', 'wallet_transactions', type_='check')
    op.drop_column('users', 'fcm_token')
