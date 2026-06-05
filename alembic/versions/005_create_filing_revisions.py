"""create filing_revisions table

Revision ID: 005
Revises: 004
Create Date: 2025-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "filing_revisions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("filing_id", sa.UUID(), sa.ForeignKey("filings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", sa.UUID(), sa.ForeignKey("organisations.id"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("generated_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),

        # Full input snapshot
        sa.Column("form16_snapshot", sa.JSON(), nullable=False),
        sa.Column("form16_2_snapshot", sa.JSON(), nullable=True),
        sa.Column("ais_snapshot", sa.JSON(), nullable=True),
        sa.Column("cg_snapshot", sa.JSON(), nullable=True),
        sa.Column("fo_snapshot", sa.JSON(), nullable=True),
        sa.Column("schedule_al_snapshot", sa.JSON(), nullable=True),
        sa.Column("manual_inputs", sa.JSON(), nullable=False),

        # Full output snapshot
        sa.Column("computation_result", sa.JSON(), nullable=False),
        sa.Column("itr_json", sa.JSON(), nullable=False),
        sa.Column("itr_form", sa.Text(), nullable=False),
        sa.Column("recommended_regime", sa.Text(), nullable=False),

        sa.Column("change_summary", sa.Text(), nullable=True),

        # Immutable — no updated_at
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),

        sa.UniqueConstraint("filing_id", "revision_number", name="uq_revisions_filing_rev"),
    )
    op.create_index("ix_filing_revisions_filing_id", "filing_revisions", ["filing_id"])
    op.create_index("ix_filing_revisions_org_id", "filing_revisions", ["org_id"])


def downgrade() -> None:
    op.drop_table("filing_revisions")
