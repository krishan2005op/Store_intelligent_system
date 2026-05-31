from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_create_retail_events"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retail_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("camera_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("track_id", sa.String(length=128), nullable=True),
        sa.Column("global_person_id", sa.String(length=128), nullable=True),
        sa.Column("person_type", sa.String(length=32), nullable=False),
        sa.Column("zone_id", sa.String(length=128), nullable=True),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_retail_events_store_id", "retail_events", ["store_id"])
    op.create_index("ix_retail_events_session_id", "retail_events", ["session_id"])
    op.create_index(
        "ix_retail_events_global_person_id",
        "retail_events",
        ["global_person_id"],
    )
    op.create_index("ix_retail_events_zone_id", "retail_events", ["zone_id"])
    op.create_index(
        "ix_retail_events_store_occurred_at",
        "retail_events",
        ["store_id", "occurred_at"],
    )
    op.create_index(
        "ix_retail_events_store_event_type",
        "retail_events",
        ["store_id", "event_type"],
    )
    op.create_index(
        "ix_retail_events_session_sequence",
        "retail_events",
        ["session_id", "sequence_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_retail_events_session_sequence", table_name="retail_events")
    op.drop_index("ix_retail_events_store_event_type", table_name="retail_events")
    op.drop_index("ix_retail_events_store_occurred_at", table_name="retail_events")
    op.drop_index("ix_retail_events_zone_id", table_name="retail_events")
    op.drop_index("ix_retail_events_global_person_id", table_name="retail_events")
    op.drop_index("ix_retail_events_session_id", table_name="retail_events")
    op.drop_index("ix_retail_events_store_id", table_name="retail_events")
    op.drop_table("retail_events")
