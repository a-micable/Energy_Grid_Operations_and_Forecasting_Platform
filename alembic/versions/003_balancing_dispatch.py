"""Add balancing and dispatch tables

Revision ID: 003
Revises: 002
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "balancing_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grid_zones.id"), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supply_mw", sa.Numeric(14, 4), nullable=False),
        sa.Column("demand_mw", sa.Numeric(14, 4), nullable=False),
        sa.Column("net_imbalance_mw", sa.Numeric(14, 4), nullable=False),
        sa.Column("frequency_hz", sa.Numeric(8, 4), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("reserve_available_mw", sa.Numeric(14, 4), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "dispatch_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grid_zones.id"), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("horizon_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_cost", sa.Numeric(16, 4)),
        sa.Column("total_emissions_kg", sa.Numeric(16, 4)),
        sa.Column("optimization_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_by", sa.String(256), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "dispatch_instructions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dispatch_plans.id"), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generation_resources.id"), nullable=False),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_output_mw", sa.Numeric(14, 4), nullable=False),
        sa.Column("actual_output_mw", sa.Numeric(14, 4)),
        sa.Column("priority", sa.Integer(), server_default="100"),
        sa.Column("status", sa.String(32), server_default="scheduled"),
        sa.Column("marginal_cost", sa.Numeric(10, 4)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("dispatch_instructions")
    op.drop_table("dispatch_plans")
    op.drop_table("balancing_snapshots")
