"""Add reserve capacity and resource capacity tables

Revision ID: 007
Revises: 006
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reserve_capacity",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grid_zones.id"), nullable=False),
        sa.Column("reserve_type", sa.String(32), nullable=False),
        sa.Column("capacity_mw", sa.Numeric(14, 4), nullable=False),
        sa.Column("committed_mw", sa.Numeric(14, 4), server_default="0"),
        sa.Column("available_mw", sa.Numeric(14, 4), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "resource_capacity",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generation_resources.id"), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_mw", sa.Numeric(14, 4), nullable=False),
        sa.Column("derated_mw", sa.Numeric(14, 4), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "balancing_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grid_zones.id"), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("balancing_snapshots.id")),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generation_resources.id")),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("target_mw", sa.Numeric(14, 4), nullable=False),
        sa.Column("actual_mw", sa.Numeric(14, 4)),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("priority", sa.Integer(), server_default="50"),
        sa.Column("initiated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("initiated_by", sa.String(256), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_balancing_actions_zone_status", "balancing_actions", ["zone_id", "status"])
    op.create_index("ix_forecast_runs_zone_type", "forecast_runs", ["zone_id", "forecast_type"])
    op.create_index("ix_audit_entries_entity", "audit_entries", ["entity_type", "entity_id"])
    op.create_index("ix_event_records_status", "event_records", ["status", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_event_records_status")
    op.drop_index("ix_audit_entries_entity")
    op.drop_index("ix_forecast_runs_zone_type")
    op.drop_index("ix_balancing_actions_zone_status")
    op.drop_table("balancing_actions")
    op.drop_table("resource_capacity")
    op.drop_table("reserve_capacity")
