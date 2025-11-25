"""Add outage and battery tables

Revision ID: 004
Revises: 003
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outage_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grid_zones.id"), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("outage_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), server_default="draft"),
        sa.Column("planned_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("planned_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_start", sa.DateTime(timezone=True)),
        sa.Column("actual_end", sa.DateTime(timezone=True)),
        sa.Column("impact_mw", sa.Float(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_by", sa.String(256), nullable=False),
        sa.Column("approved_by", sa.String(256)),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "battery_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generation_resources.id"), unique=True),
        sa.Column("name_capacity_mwh", sa.Numeric(12, 4), nullable=False),
        sa.Column("usable_capacity_mwh", sa.Numeric(12, 4), nullable=False),
        sa.Column("max_charge_mw", sa.Numeric(12, 4), nullable=False),
        sa.Column("max_discharge_mw", sa.Numeric(12, 4), nullable=False),
        sa.Column("state_of_charge_pct", sa.Numeric(6, 4), nullable=False),
        sa.Column("state", sa.String(32), server_default="idle"),
        sa.Column("cycle_count", sa.Integer(), server_default="0"),
        sa.Column("degradation_pct", sa.Numeric(6, 4), server_default="0"),
        sa.Column("round_trip_efficiency", sa.Numeric(5, 4), server_default="0.90"),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("battery_assets")
    op.drop_table("outage_plans")
