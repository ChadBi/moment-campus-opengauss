"""地点稳定资料提议与 AI 摘要版本（LOC-02）。"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "z5e6f7g8h9i0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "location_facts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("location_id", sa.BigInteger(), sa.ForeignKey("locations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", sa.BigInteger(), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fact_key", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_location_facts_location", "location_facts", ["location_id", "is_active", "sort_order"])
    op.create_index("idx_location_facts_school_key", "location_facts", ["school_id", "fact_key"])

    op.create_table(
        "location_fact_proposals",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("location_id", sa.BigInteger(), sa.ForeignKey("locations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", sa.BigInteger(), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposer_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("changes_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reviewer_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_location_fact_proposals_queue", "location_fact_proposals", ["school_id", "status", "created_at"])
    op.create_index("idx_location_fact_proposals_user_status", "location_fact_proposals", ["proposer_id", "status"])

    op.create_table(
        "location_summary_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("location_id", sa.BigInteger(), sa.ForeignKey("locations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", sa.BigInteger(), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending_review"),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("confidence_level", sa.String(length=20), nullable=False, server_default="insufficient"),
        sa.Column("claims_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("conflicts_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_refs_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("stale_at", sa.DateTime(), nullable=True),
        sa.Column("ai_log_id", sa.BigInteger(), sa.ForeignKey("ai_invocation_logs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewer_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_location_summary_queue", "location_summary_versions", ["school_id", "status", "generated_at"])
    op.create_index("idx_location_summary_location_version", "location_summary_versions", ["location_id", "version"])
    op.create_index("idx_location_summary_source_hash", "location_summary_versions", ["location_id", "source_hash"])

    op.add_column("locations", sa.Column("current_summary_id", sa.BigInteger(), nullable=True))
    op.add_column("locations", sa.Column("summary_dirty_at", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        "fk_locations_current_summary", "locations", "location_summary_versions",
        ["current_summary_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("idx_locations_summary_dirty", "locations", ["summary_dirty_at"])


def downgrade() -> None:
    op.drop_index("idx_locations_summary_dirty", table_name="locations")
    op.drop_constraint("fk_locations_current_summary", "locations", type_="foreignkey")
    op.drop_column("locations", "summary_dirty_at")
    op.drop_column("locations", "current_summary_id")
    op.drop_index("idx_location_summary_source_hash", table_name="location_summary_versions")
    op.drop_index("idx_location_summary_location_version", table_name="location_summary_versions")
    op.drop_index("idx_location_summary_queue", table_name="location_summary_versions")
    op.drop_table("location_summary_versions")
    op.drop_index("idx_location_fact_proposals_user_status", table_name="location_fact_proposals")
    op.drop_index("idx_location_fact_proposals_queue", table_name="location_fact_proposals")
    op.drop_table("location_fact_proposals")
    op.drop_index("idx_location_facts_school_key", table_name="location_facts")
    op.drop_index("idx_location_facts_location", table_name="location_facts")
    op.drop_table("location_facts")
