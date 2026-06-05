"""create clients table

Revision ID: 003
Revises: 002
Create Date: 2025-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", sa.UUID(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pan", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("mobile", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "pan", name="uq_clients_org_pan"),
    )
    op.create_index("ix_clients_org_id", "clients", ["org_id"])
    op.create_index("ix_clients_pan", "clients", ["pan"])


def downgrade() -> None:
    op.drop_table("clients")
