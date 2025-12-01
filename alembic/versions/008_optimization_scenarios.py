"""Add optimization scenarios and compliance reports

Revision ID: 008
Revises: 007
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "optimization_scenarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("optimization_runs.id"), nullable=False),
        sa.Column("scenario_name", sa.String(256), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), server_default="{}"),
        sa.Column("objective_value", sa.Numeric(18, 6)),
        sa.Column("solution", postgresql.JSONB(), server_default="{}"),
        sa.Column("rank", sa.Integer()),
        sa.Column("is_selected", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "compliance_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("report_type", sa.String(64), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), server_default="draft"),
        sa.Column("generated_by", sa.String(256), nullable=False),
        sa.Column("content", postgresql.JSONB(), server_default="{}"),
        sa.Column("findings", postgresql.JSONB(), server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "event_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("handler_name", sa.String(256), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("filter_expression", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_foreign_key(
        "fk_battery_schedules_opt",
        "battery_schedules",
        "optimization_runs",
        ["optimization_run_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_dispatch_plans_opt",
        "dispatch_plans",
        "optimization_runs",
        ["optimization_run_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_dispatch_plans_opt", "dispatch_plans", type_="foreignkey")
    op.drop_constraint("fk_battery_schedules_opt", "battery_schedules", type_="foreignkey")
    op.drop_table("event_subscriptions")
    op.drop_table("compliance_reports")
    op.drop_table("optimization_scenarios")
