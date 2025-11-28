"""Add events, audit, and optimization tables

Revision ID: 005
Revises: 004
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("aggregate_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("retry_count", sa.Integer(), server_default="0"),
        sa.Column("routing_key", sa.String(128), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("sequence_number", sa.Integer()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "audit_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(256), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("before_state", postgresql.JSONB()),
        sa.Column("after_state", postgresql.JSONB()),
        sa.Column("reason", sa.Text()),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "optimization_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grid_zones.id"), nullable=False),
        sa.Column("run_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("objective_value", sa.Numeric(18, 6)),
        sa.Column("constraints", postgresql.JSONB(), server_default="{}"),
        sa.Column("solution", postgresql.JSONB(), server_default="{}"),
        sa.Column("solver_name", sa.String(64), server_default="scipy_milp"),
        sa.Column("solver_status", sa.String(32)),
        sa.Column("error_message", sa.Text()),
        sa.Column("timeout_seconds", sa.Integer(), server_default="120"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("optimization_runs")
    op.drop_table("audit_entries")
    op.drop_table("event_records")
