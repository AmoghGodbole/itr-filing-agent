"""SQLAlchemy ORM models — one class per DB table."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Date, ForeignKey, Integer, JSON, Numeric,
    Text, TIMESTAMP, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Organisation(Base):
    __tablename__ = "organisations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    users: Mapped[list["User"]] = relationship("User", back_populates="org", cascade="all, delete-orphan")
    clients: Mapped[list["Client"]] = relationship("Client", back_populates="org", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, server_default="member", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    org: Mapped["Organisation"] = relationship("Organisation", back_populates="users")


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (UniqueConstraint("org_id", "pan", name="uq_clients_org_pan"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    pan: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    org: Mapped["Organisation"] = relationship("Organisation", back_populates="clients")
    filings: Mapped[list["Filing"]] = relationship("Filing", back_populates="client", cascade="all, delete-orphan")


class Filing(Base):
    __tablename__ = "filings"
    __table_args__ = (UniqueConstraint("client_id", "assessment_year", name="uq_filings_client_ay"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    assessment_year: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, server_default="draft", nullable=False, index=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True, index=True)
    last_modified_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    # Manual inputs
    hra_monthly_rent: Mapped[float] = mapped_column(Numeric(12, 2), server_default="0", nullable=False)
    hra_city: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    parents_insurance_premium: Mapped[float] = mapped_column(Numeric(12, 2), server_default="0", nullable=False)
    parents_senior: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    home_loan_interest_cert: Mapped[float] = mapped_column(Numeric(12, 2), server_default="0", nullable=False)
    rental_annual_rent: Mapped[float] = mapped_column(Numeric(12, 2), server_default="0", nullable=False)
    rental_municipal_taxes: Mapped[float] = mapped_column(Numeric(12, 2), server_default="0", nullable=False)
    rental_home_loan_interest: Mapped[float] = mapped_column(Numeric(12, 2), server_default="0", nullable=False)
    family_pension: Mapped[float] = mapped_column(Numeric(12, 2), server_default="0", nullable=False)
    home_loan_80eea: Mapped[float] = mapped_column(Numeric(12, 2), server_default="0", nullable=False)
    date_of_birth: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    aadhaar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bank_account_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bank_ifsc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bank_account_type: Mapped[str] = mapped_column(Text, server_default="Savings", nullable=False)

    # Parsed data (raw from Claude)
    parsed_form16_raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    parsed_form16_2_raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    parsed_ais_raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    parsed_form26as_raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    parsed_cg_raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    parsed_fo_raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # CA-reviewed data
    form16_reviewed: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    form16_2_reviewed: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ais_reviewed: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    cg_reviewed: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    fo_reviewed: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    schedule_al: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Output
    computation_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    itr_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    itr_form: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_regime: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Post-filing
    acknowledgement_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    filed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    filed_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    client: Mapped["Client"] = relationship("Client", back_populates="filings")
    revisions: Mapped[list["FilingRevision"]] = relationship("FilingRevision", back_populates="filing", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="filing", cascade="all, delete-orphan")


class FilingRevision(Base):
    __tablename__ = "filing_revisions"
    __table_args__ = (UniqueConstraint("filing_id", "revision_number", name="uq_revisions_filing_rev"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    filing_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("filings.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("organisations.id"), nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)

    # Input snapshot
    form16_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    form16_2_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ais_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    cg_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    fo_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    schedule_al_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    manual_inputs: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Output snapshot
    computation_result: Mapped[dict] = mapped_column(JSON, nullable=False)
    itr_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    itr_form: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_regime: Mapped[str] = mapped_column(Text, nullable=False)

    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    filing: Mapped["Filing"] = relationship("Filing", back_populates="revisions")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    filing_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("filings.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("organisations.id"), nullable=False, index=True)
    uploaded_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    doc_type: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parse_status: Mapped[str] = mapped_column(Text, server_default="pending", nullable=False)
    parsed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    parse_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    filing: Mapped["Filing"] = relationship("Filing", back_populates="documents")
