"""refresh_token_device_binding: device_id column on refresh_tokens

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-07-28 12:00:00.000000+00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('refresh_tokens', sa.Column('device_id', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('refresh_tokens', 'device_id')
