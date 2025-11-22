"""Initial GridMind schema

Revision ID: 001
Revises:
Create Date: 2025-06-15 10:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "grid_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), unique=True, nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("region", sa.String(128), nullable=False),
        sa.Column("timezone", sa.String(64), server_default="UTC"),
        sa.Column("peak_demand_mw", sa.Numeric(12, 3), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_grid_zones_code", "grid_zones", ["code"])

    op.create_table(
        "generation_resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grid_zones.id"), nullable=False),
        sa.Column("code", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("capacity_mw", sa.Numeric(12, 3), nullable=False),
        sa.Column("min_output_mw", sa.Numeric(12, 3), server_default="0"),
        sa.Column("ramp_rate_mw_per_min", sa.Numeric(10, 3), server_default="1"),
        sa.Column("marginal_cost_per_mwh", sa.Numeric(10, 4), nullable=False),
        sa.Column("emission_rate_kg_co2_per_mwh", sa.Numeric(10, 4), server_default="0"),
        sa.Column("dispatch_priority", sa.Integer(), server_default="100"),
        sa.Column("is_available", sa.Boolean(), server_default="true"),
        sa.Column("is_renewable", sa.Boolean(), server_default="false"),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("generation_resources")
    op.drop_table("grid_zones")
