"""Persist pre-ride destination/accepted fare and prevent concurrent open rides."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.types import GUID

revision: str = "20261013_0001"
down_revision: Union[str, None] = "a7c3e9d41b52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rides", sa.Column("planned_end_dock_id", GUID(), nullable=True))
    op.add_column(
        "rides",
        sa.Column("accepted_fare_amount", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column("rides", sa.Column("accepted_fare_currency", sa.String(length=10), nullable=True))
    op.add_column("rides", sa.Column("accepted_pricing_strategy", sa.String(length=50), nullable=True))
    op.add_column("rides", sa.Column("accepted_pricing_reference_id", GUID(), nullable=True))
    op.create_foreign_key(
        "fk_rides_planned_end_dock_id_docks", "rides", "docks",
        ["planned_end_dock_id"], ["id"], ondelete="RESTRICT",
    )
    # A partial unique index makes the invariant database-enforced on both
    # PostgreSQL and SQLite (used by the focused test suite).
    op.create_index(
        "uq_rides_one_open_per_user", "rides", ["user_id"], unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'ACTIVE')"),
        sqlite_where=sa.text("status IN ('PENDING', 'ACTIVE')"),
    )


def downgrade() -> None:
    op.drop_index("uq_rides_one_open_per_user", table_name="rides")
    op.drop_constraint("fk_rides_planned_end_dock_id_docks", "rides", type_="foreignkey")
    for name in (
        "accepted_pricing_reference_id", "accepted_pricing_strategy",
        "accepted_fare_currency", "accepted_fare_amount", "planned_end_dock_id",
    ):
        op.drop_column("rides", name)
