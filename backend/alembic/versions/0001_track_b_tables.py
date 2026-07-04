"""track b core tables

Revision ID: 0001
Revises:
Create Date: 2026-07-02
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("firebase_uid", sa.String(255), nullable=False, unique=True),
        sa.Column("phone_number", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(255)),
        sa.Column("role", sa.String(20), nullable=False, server_default="USER"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_users_phone", "users", ["phone_number"])
    op.create_index("idx_users_firebase_uid", "users", ["firebase_uid"])

    op.create_table(
        "docks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("latitude", sa.Float, nullable=False),
        sa.Column("longitude", sa.Float, nullable=False),
        sa.Column("total_slots", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "vehicles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("qr_code", sa.String(255), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="AVAILABLE"),
        sa.Column("battery_pct", sa.Integer),
        sa.Column("dock_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("docks.id")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "dock_slots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dock_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("docks.id"), nullable=False),
        sa.Column("slot_number", sa.Integer, nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id")),
        sa.Column("is_occupied", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_charging", sa.Boolean, nullable=False, server_default="false"),
    )

    op.create_table(
        "wallets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "wallet_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wallets.id"), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("reference_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_wallet_txn_wallet", "wallet_transactions", ["wallet_id"])
    op.create_index("idx_wallet_txn_reference", "wallet_transactions", ["reference_id"])
    op.create_check_constraint("ck_wallet_txn_amount_positive", "wallet_transactions", "amount > 0")

    op.create_table(
        "rides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id")),
        sa.Column("dock_start_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("docks.id")),
        sa.Column("dock_end_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("docks.id")),
        sa.Column("status", sa.String(30), nullable=False, server_default="REQUESTED"),
        sa.Column("fare", sa.Numeric(10, 2)),
        sa.Column("start_at", sa.DateTime(timezone=True)),
        sa.Column("end_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "ride_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ride_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rides.id"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "vehicle_status",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("battery_pct", sa.Integer),
        sa.Column("location", sa.JSON),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.Column("payload", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_refresh_tokens_user", "refresh_tokens", ["user_id"])
    op.create_index("idx_refresh_tokens_expiry", "refresh_tokens", ["expires_at"])
    op.create_index("idx_refresh_tokens_hash", "refresh_tokens", ["token_hash"])
    op.create_index("idx_refresh_tokens_family", "refresh_tokens", ["family_id"])


def downgrade() -> None:
    for table in [
        "refresh_tokens", "audit_logs", "notifications", "vehicle_status", "ride_events", "rides",
        "wallet_transactions", "wallets", "dock_slots", "vehicles", "docks", "users",
    ]:
        op.drop_table(table)
