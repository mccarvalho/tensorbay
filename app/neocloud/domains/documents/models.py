"""SQLAlchemy models for AI-generated commercial/legal documents.

Supports the AI Document Generation feature: MSA, LOI, Proposal and Contract
drafts produced via Amazon Bedrock. Generated legal documents always start as
drafts (status GENERATED) and require explicit human approval (section 21
audit trail applies to every status change).
"""

from enum import StrEnum

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from neocloud.db.base import AuditMixin, Base, TenantMixin, UUIDMixin


class DocType(StrEnum):
    MSA = "MSA"
    LOI = "LOI"
    PROPOSAL = "PROPOSAL"
    CONTRACT = "CONTRACT"


class DocumentStatus(StrEnum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# Store enums as portable VARCHARs (native_enum=False) using the member *value*.
# This keeps values round-tripping as enum members on read across SQLite/Postgres.
_doc_type_enum = Enum(
    DocType, name="doc_type", native_enum=False, length=32, values_callable=lambda e: [m.value for m in e]
)
_doc_status_enum = Enum(
    DocumentStatus, name="document_status", native_enum=False, length=32, values_callable=lambda e: [m.value for m in e]
)


class GeneratedDocument(Base, UUIDMixin, AuditMixin, TenantMixin):
    __tablename__ = "generated_documents"

    doc_type: Mapped[DocType] = mapped_column(_doc_type_enum, nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    contract_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        _doc_status_enum, nullable=False, default=DocumentStatus.GENERATED
    )
    s3_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class DocumentTemplate(Base, UUIDMixin, AuditMixin):
    __tablename__ = "document_templates"

    doc_type: Mapped[DocType] = mapped_column(
        _doc_type_enum, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
