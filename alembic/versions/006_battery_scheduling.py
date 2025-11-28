"""Add battery scheduling and cycle tables

Revision ID: 006
Revises: 005
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "battery_cycles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("battery_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("battery_assets.id"), nullable=False),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("energy_charged_mwh", sa.Numeric(12, 4), server_default="0"),
        sa.Column("energy_discharged_mwh", sa.Numeric(12, 4), server_default="0"),
        sa.Column("depth_of_discharge_pct", sa.Numeric(6, 4), server_default="0"),
        sa.Column("degradation_delta_pct", sa.Numeric(8, 6), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "battery_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("battery_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("battery_assets.id"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("target_power_mw", sa.Numeric(12, 4), nullable=False),
        sa.Column("target_soc_pct", sa.Numeric(6, 4)),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), server_default="scheduled"),
        sa.Column("optimization_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("is_emergency", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "outage_resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("outage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("outage_plans.id"), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generation_resources.id"), nullable=False),
        sa.Column("role", sa.String(64), server_default="affected"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("outage_id", "resource_id", name="uq_outage_resource"),
    )
    op.create_table(
        "outage_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("outage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("outage_plans.id"), nullable=False),
        sa.Column("depends_on_outage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("outage_plans.id"), nullable=False),
        sa.Column("dependency_type", sa.String(64), nullable=False),
        sa.Column("is_hard", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("outage_id", "depends_on_outage_id", name="uq_outage_dependency"),
    )


def downgrade() -> None:
    op.drop_table("outage_dependencies")
    op.drop_table("outage_resources")
    op.drop_table("battery_schedules")
    op.drop_table("battery_cycles")
