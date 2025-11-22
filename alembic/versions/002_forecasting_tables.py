"""Add forecasting tables

Revision ID: 002
Revises: 001
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "forecast_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grid_zones.id"), nullable=False),
        sa.Column("forecast_type", sa.String(32), nullable=False),
        sa.Column("horizon", sa.String(16), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.Column("parameters", postgresql.JSONB(), server_default="{}"),
        sa.Column("metrics", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "forecast_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("forecast_runs.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default="true"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence_level", sa.Numeric(5, 4), server_default="0.95"),
        sa.Column("revision_reason", sa.Text()),
        sa.Column("superseded_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("forecast_versions.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "version_number", name="uq_forecast_version"),
    )
    op.create_table(
        "forecast_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("forecast_versions.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value_mw", sa.Numeric(14, 4), nullable=False),
        sa.Column("lower_bound_mw", sa.Numeric(14, 4)),
        sa.Column("upper_bound_mw", sa.Numeric(14, 4)),
        sa.Column("actual_mw", sa.Numeric(14, 4)),
        sa.UniqueConstraint("version_id", "timestamp", name="uq_forecast_point_timestamp"),
    )
    op.create_table(
        "forecast_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("forecast_versions.id"), nullable=False),
        sa.Column("previous_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("forecast_versions.id"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("delta_pct", sa.Numeric(8, 4), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("revised_by", sa.String(256), nullable=False),
        sa.Column("drift_flagged", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("forecast_revisions")
    op.drop_table("forecast_points")
    op.drop_table("forecast_versions")
    op.drop_table("forecast_runs")
