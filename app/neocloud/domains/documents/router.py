"""HTTP router for the documents module.

Endpoints:
  POST   /documents/generate          generate a draft via Bedrock (DOCUMENT_GENERATE)
  GET    /documents                   list generated documents (CONTRACT_READ)
  GET    /documents/templates         list templates (CONTRACT_READ)
  POST   /documents/templates         create a template (CONTRACT_WRITE)
  GET    /documents/templates/{id}    fetch one template (CONTRACT_READ)
  PATCH  /documents/templates/{id}    update a template (CONTRACT_WRITE)
  DELETE /documents/templates/{id}    delete a template (CONTRACT_WRITE)
  GET    /documents/{id}              fetch one generated document (CONTRACT_READ)
  POST   /documents/{id}/approve      approve a draft (CONTRACT_WRITE)
  POST   /documents/{id}/reject       reject a draft (CONTRACT_WRITE)

The static ``/templates`` routes are declared before the dynamic
``/{document_id}`` routes so they are matched first by FastAPI.

Generated legal documents always start as GENERATED drafts and require an
explicit human approve/reject action.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.core.config import get_settings
from neocloud.db.session import get_session
from neocloud.domains.documents.models import (
    DocType,
    DocumentStatus,
    DocumentTemplate,
    GeneratedDocument,
)
from neocloud.domains.documents.schemas import (
    DocumentTemplateCreate,
    DocumentTemplateResponse,
    DocumentTemplateUpdate,
    GeneratedDocumentResponse,
    GeneratedDocumentWithContent,
    GenerateDocumentRequest,
)
from neocloud.domains.documents.service import BedrockDocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


# Fallback prompt templates used when no stored template or inline body is given.
DEFAULT_TEMPLATES: dict[DocType, str] = {
    DocType.MSA: (
        "Draft a Master Services Agreement (MSA) for GPU cloud services. "
        "Include parties, definitions, scope of services, term and renewal, "
        "fees and payment, service levels, data protection, liability, "
        "confidentiality, termination, and governing law."
    ),
    DocType.LOI: (
        "Draft a non-binding Letter of Intent (LOI) for a GPU capacity "
        "engagement. Summarize the intended commitment, indicative pricing, "
        "term, exclusivity (if any), and next steps toward a definitive "
        "agreement."
    ),
    DocType.PROPOSAL: (
        "Draft a commercial Proposal for GPU cloud capacity. Include an "
        "executive summary, proposed configuration, pricing, committed term, "
        "SLA highlights, and assumptions."
    ),
    DocType.CONTRACT: (
        "Draft a definitive service Contract for GPU cloud capacity based on "
        "the provided commercial terms. Include ordering details, committed "
        "capacity, pricing schedule, SLA, term, and signature blocks."
    ),
}


def _prompt_summary(doc_type: DocType, context: dict) -> str:
    keys = ", ".join(sorted(context)) if context else "none"
    return f"doc_type={doc_type.value}; context_keys={keys}"


# --- Generation --------------------------------------------------------------


@router.post(
    "/generate",
    response_model=GeneratedDocumentWithContent,
    status_code=status.HTTP_201_CREATED,
)
async def generate_document(
    payload: GenerateDocumentRequest,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.DOCUMENT_GENERATE)),
) -> GeneratedDocumentWithContent:
    # Resolve the template body: stored template > inline body > default.
    template_body: str
    if payload.template_id:
        template = await session.get(DocumentTemplate, payload.template_id)
        if template is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            )
        template_body = template.body
    elif payload.template_body:
        template_body = payload.template_body
    else:
        template_body = DEFAULT_TEMPLATES[payload.doc_type]

    settings = get_settings()
    service = BedrockDocumentService(settings)
    content, s3_key = service.generate(
        payload.doc_type.value, payload.context, template_body
    )

    document = GeneratedDocument(
        doc_type=payload.doc_type,
        customer_id=payload.customer_id,
        contract_id=payload.contract_id,
        title=payload.title,
        status=DocumentStatus.GENERATED,  # always a draft; human review required
        s3_key=s3_key,
        model_id=settings.bedrock_model_id,
        prompt_summary=_prompt_summary(payload.doc_type, payload.context),
        tenant_id=user.tenant_id,
        created_by=user.subject,
        updated_by=user.subject,
    )
    session.add(document)
    await session.flush()

    await record_audit(
        session,
        action="generate",
        entity_type="GeneratedDocument",
        entity_id=document.id,
        actor=user.subject,
        new_value={
            "doc_type": document.doc_type.value,
            "status": document.status.value,
            "s3_key": document.s3_key,
        },
    )

    base = GeneratedDocumentResponse.model_validate(document)
    return GeneratedDocumentWithContent(**base.model_dump(), content=content)


# --- Generated documents: list ----------------------------------------------


@router.get("", response_model=list[GeneratedDocumentResponse])
async def list_documents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    doc_type: DocType | None = None,
    document_status: DocumentStatus | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CONTRACT_READ)),
) -> list[GeneratedDocument]:
    stmt = select(GeneratedDocument)
    if doc_type is not None:
        stmt = stmt.where(GeneratedDocument.doc_type == doc_type)
    if document_status is not None:
        stmt = stmt.where(GeneratedDocument.status == document_status)
    stmt = stmt.order_by(GeneratedDocument.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


# --- Templates CRUD ----------------------------------------------------------
# Declared before the dynamic /{document_id} routes so "/templates" is not
# captured as a document id.


@router.get("/templates", response_model=list[DocumentTemplateResponse])
async def list_templates(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    doc_type: DocType | None = None,
    active: bool | None = None,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CONTRACT_READ)),
) -> list[DocumentTemplate]:
    stmt = select(DocumentTemplate)
    if doc_type is not None:
        stmt = stmt.where(DocumentTemplate.doc_type == doc_type)
    if active is not None:
        stmt = stmt.where(DocumentTemplate.active == active)
    stmt = stmt.order_by(DocumentTemplate.name).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post(
    "/templates",
    response_model=DocumentTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    payload: DocumentTemplateCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> DocumentTemplate:
    template = DocumentTemplate(
        doc_type=payload.doc_type,
        name=payload.name,
        body=payload.body,
        active=payload.active,
        created_by=user.subject,
        updated_by=user.subject,
    )
    session.add(template)
    await session.flush()

    await record_audit(
        session,
        action="create",
        entity_type="DocumentTemplate",
        entity_id=template.id,
        actor=user.subject,
        new_value={
            "doc_type": template.doc_type.value,
            "name": template.name,
            "active": template.active,
        },
    )
    return template


@router.get("/templates/{template_id}", response_model=DocumentTemplateResponse)
async def get_template(
    template_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CONTRACT_READ)),
) -> DocumentTemplate:
    template = await session.get(DocumentTemplate, template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )
    return template


@router.patch("/templates/{template_id}", response_model=DocumentTemplateResponse)
async def update_template(
    template_id: str,
    payload: DocumentTemplateUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> DocumentTemplate:
    template = await session.get(DocumentTemplate, template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )

    old_value = {
        "name": template.name,
        "body": template.body,
        "active": template.active,
    }
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(template, key, value)
    template.updated_by = user.subject

    await record_audit(
        session,
        action="update",
        entity_type="DocumentTemplate",
        entity_id=template.id,
        actor=user.subject,
        old_value=old_value,
        new_value=updates,
    )
    return template


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> None:
    template = await session.get(DocumentTemplate, template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )

    await record_audit(
        session,
        action="delete",
        entity_type="DocumentTemplate",
        entity_id=template.id,
        actor=user.subject,
        old_value={
            "doc_type": template.doc_type.value,
            "name": template.name,
        },
    )
    await session.delete(template)


# --- Generated documents: read + approval workflow --------------------------


@router.get("/{document_id}", response_model=GeneratedDocumentResponse)
async def get_document(
    document_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CONTRACT_READ)),
) -> GeneratedDocument:
    document = await session.get(GeneratedDocument, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return document


async def _transition_status(
    document_id: str,
    new_status: DocumentStatus,
    action: str,
    session: AsyncSession,
    user: CurrentUser,
) -> GeneratedDocument:
    document = await session.get(GeneratedDocument, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    old_status = document.status
    document.status = new_status
    document.updated_by = user.subject

    await record_audit(
        session,
        action=action,
        entity_type="GeneratedDocument",
        entity_id=document.id,
        actor=user.subject,
        old_value={"status": old_status.value},
        new_value={"status": new_status.value},
    )
    return document


@router.post("/{document_id}/approve", response_model=GeneratedDocumentResponse)
async def approve_document(
    document_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> GeneratedDocument:
    return await _transition_status(
        document_id, DocumentStatus.APPROVED, "approve", session, user
    )


@router.post("/{document_id}/reject", response_model=GeneratedDocumentResponse)
async def reject_document(
    document_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> GeneratedDocument:
    return await _transition_status(
        document_id, DocumentStatus.REJECTED, "reject", session, user
    )
