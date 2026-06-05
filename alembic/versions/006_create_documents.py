"""create documents table

Revision ID: 006
Revises: 005
Create Date: 2025-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("filing_id", sa.UUID(), sa.ForeignKey("filings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", sa.UUID(), sa.ForeignKey("organisations.id"), nullable=False),
        sa.Column("uploaded_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("doc_type", sa.Text(), nullable=False),
        sa.Column("original_name", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False, unique=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("parse_status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("parsed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_filing_id", "documents", ["filing_id"])
    op.create_index("ix_documents_org_id", "documents", ["org_id"])
    op.create_index("ix_documents_storage_key", "documents", ["storage_key"], unique=True)


def downgrade() -> None:
    op.drop_table("documents")
