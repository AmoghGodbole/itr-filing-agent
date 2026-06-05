"""create filings table

Revision ID: 004
Revises: 003
Create Date: 2025-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "filings",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", sa.UUID(), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.UUID(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assessment_year", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("assigned_to", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("last_modified_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),

        # Manual inputs
        sa.Column("hra_monthly_rent", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("hra_city", sa.Text(), server_default="", nullable=False),
        sa.Column("parents_insurance_premium", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("parents_senior", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("home_loan_interest_cert", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("rental_annual_rent", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("rental_municipal_taxes", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("rental_home_loan_interest", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("family_pension", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("home_loan_80eea", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("date_of_birth", sa.Text(), server_default="", nullable=False),
        sa.Column("aadhaar", sa.Text(), nullable=True),
        sa.Column("mobile", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("bank_account_number", sa.Text(), nullable=True),
        sa.Column("bank_ifsc", sa.Text(), nullable=True),
        sa.Column("bank_name", sa.Text(), nullable=True),
        sa.Column("bank_account_type", sa.Text(), server_default="Savings", nullable=False),

        # Parsed data (raw from Claude)
        sa.Column("parsed_form16_raw", sa.JSON(), nullable=True),
        sa.Column("parsed_form16_2_raw", sa.JSON(), nullable=True),
        sa.Column("parsed_ais_raw", sa.JSON(), nullable=True),
        sa.Column("parsed_form26as_raw", sa.JSON(), nullable=True),
        sa.Column("parsed_cg_raw", sa.JSON(), nullable=True),
        sa.Column("parsed_fo_raw", sa.JSON(), nullable=True),

        # CA-reviewed data
        sa.Column("form16_reviewed", sa.JSON(), nullable=True),
        sa.Column("form16_2_reviewed", sa.JSON(), nullable=True),
        sa.Column("ais_reviewed", sa.JSON(), nullable=True),
        sa.Column("cg_reviewed", sa.JSON(), nullable=True),
        sa.Column("fo_reviewed", sa.JSON(), nullable=True),
        sa.Column("schedule_al", sa.JSON(), nullable=True),

        # Output
        sa.Column("computation_result", sa.JSON(), nullable=True),
        sa.Column("itr_json", sa.JSON(), nullable=True),
        sa.Column("itr_form", sa.Text(), nullable=True),
        sa.Column("recommended_regime", sa.Text(), nullable=True),

        # Post-filing
        sa.Column("acknowledgement_number", sa.Text(), nullable=True),
        sa.Column("filed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("filed_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),

        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),

        sa.UniqueConstraint("client_id", "assessment_year", name="uq_filings_client_ay"),
    )
    op.create_index("ix_filings_org_id", "filings", ["org_id"])
    op.create_index("ix_filings_client_id", "filings", ["client_id"])
    op.create_index("ix_filings_status", "filings", ["status"])
    op.create_index("ix_filings_assigned_to", "filings", ["assigned_to"])
    op.create_index("ix_filings_assessment_year", "filings", ["assessment_year"])


def downgrade() -> None:
    op.drop_table("filings")
