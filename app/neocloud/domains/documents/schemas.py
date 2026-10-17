"""Pydantic v2 schemas for the documents module."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from neocloud.domains.documents.models import DocType, DocumentStatus


# --- Generated documents ----------------------------------------------------


class GenerateDocumentRequest(BaseModel):
    doc_type: DocType
    title: str = Field(min_length=1, max_length=255)
    customer_id: str | None = None
    contract_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    # Provide either a stored template id or an inline template body. If neither
    # is given, a sensible per-doc-type default is used by the router.
    template_id: str | None = None
    template_body: str | None = None


class GeneratedDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    doc_type: DocType
    title: str
    status: DocumentStatus
    customer_id: str | None
    contract_id: str | None
    s3_key: str | None
    model_id: str
    prompt_summary: str | None
    tenant_id: str | None
    created_at: datetime
    updated_at: datetime
    created_by: str | None
    updated_by: str | None


class GeneratedDocumentWithContent(GeneratedDocumentResponse):
    """Returned by the generate endpoint, including the freshly rendered text."""

    content: str


# --- Templates ---------------------------------------------------------------


class DocumentTemplateCreate(BaseModel):
    doc_type: DocType
    name: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    active: bool = True


class DocumentTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = Field(default=None, min_length=1)
    active: bool | None = None


class DocumentTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    doc_type: DocType
    name: str
    body: str
    active: bool
    created_at: datetime
    updated_at: datetime
    created_by: str | None
    updated_by: str | None
