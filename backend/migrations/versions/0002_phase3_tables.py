"""ride/vehicle/dock/audit tables — phase 3

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-07 00:00:00.000000

Reference: Track B branch schema (docks/vehicles/dock_slots/rides/
ride_events/audit_logs) — Track A owns these tables now since Track A/B
not merged. Column shapes match Track B exactly, no invention.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    op.create_index("idx_docks_status", "docks", ["status"])

    op.create_table(
        "vehicles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("qr_code", sa.String(255), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="AVAILABLE"),
        sa.Column("battery_pct", sa.Integer, nullable=True),
        sa.Column("dock_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("docks.id"), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_vehicles_qr_code", "vehicles", ["qr_code"])
    op.create_index("idx_vehicles_status", "vehicles", ["status"])
    op.create_index("idx_vehicles_dock", "vehicles", ["dock_id"])

    op.create_table(
        "dock_slots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dock_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("docks.id"), nullable=False),
        sa.Column("slot_number", sa.Integer, nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=True),
        sa.Column("is_occupied", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_charging", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("idx_dock_slots_dock", "dock_slots", ["dock_id"])

    op.create_table(
        "rides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=True),
        sa.Column("dock_start_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("docks.id"), nullable=True),
        sa.Column("dock_end_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("docks.id"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="REQUESTED"),
        sa.Column("fare", sa.Numeric(10, 2), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_rides_user", "rides", ["user_id"])
    op.create_index("idx_rides_vehicle", "rides", ["vehicle_id"])
    op.create_index("idx_rides_status", "rides", ["status"])

    op.create_table(
        "ride_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ride_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rides.id"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_ride_events_ride", "ride_events", ["ride_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.Column("payload", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_audit_logs_actor", "audit_logs", ["actor_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("ride_events")
    op.drop_table("rides")
    op.drop_table("dock_slots")
    op.drop_table("vehicles")
    op.drop_table("docks")
