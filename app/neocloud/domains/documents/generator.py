"""Generate a deal document, save it as DOCX and file it in Google Drive."""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.core.config import Settings, get_settings
from neocloud.core.logging import get_logger
from neocloud.db.session import get_sessionmaker
from neocloud.domains.documents import deal, forms, kb, prompts, render
from neocloud.domains.documents.models import DocType, DocumentStatus, GeneratedDocument
from neocloud.domains.documents.service import BedrockDocumentService
from neocloud.domains.drive import service as drive_service
from neocloud.domains.drive.service import DOCX_MIME, DriveError  # noqa: F401

logger = get_logger(__name__)

# English folder name per document type, under Clients/<customer>/<YYYY-MM-deal>/
TYPE_FOLDER: dict[str, str] = {
    "MSA": "MSA", "ORDER_FORM": "Order Form", "NDA": "NDA", "PROPOSAL": "Proposal",
    "POC_AGREEMENT": "PoC Agreement", "ESCROW_AGREEMENT": "Escrow Agreement",
    "ACCEPTANCE_NOTICE": "Acceptance Notice", "LOI": "LOI", "CONTRACT": "Contract",
}
TYPE_TITLE: dict[str, str] = {
    "MSA": "Master Services Agreement", "ORDER_FORM": "Order Form", "NDA": "NDA", "PROPOSAL": "Proposal",
    "POC_AGREEMENT": "PoC Agreement", "ESCROW_AGREEMENT": "Escrow Agreement",
    "ACCEPTANCE_NOTICE": "Acceptance Notice", "LOI": "Letter of Intent", "CONTRACT": "Contract",
}
FILLED_FORMS = {"MSA", "NDA"}  # standard forms filled in, never rewritten by AI


def file_name_for(doc_type: str, customer: str, version: int, today: datetime | None = None) -> str:
    d = today or datetime.now(UTC)
    return f"{TYPE_TITLE.get(doc_type, doc_type)} - {customer} - v{version} - {d:%Y-%m-%d}.docx"


def _spec_names(base: kb.KnowledgeBase, gpu_model: str) -> list[str]:
    m = gpu_model.upper().replace(" ", "")
    tokens = [t for t in ("GB200", "GB300", "VR200", "B300", "B200", "A100", "RTX") if t in m][:1]
    return [n for n in base.text_names() if "Spec" in n and tokens and tokens[0] in n.upper()][:2]


def _references(base: kb.KnowledgeBase, doc_type: str, gpu_model: str) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    specs = _spec_names(base, gpu_model)
    refs += [(n, base.text(n, 6000)) for n in specs]
    if doc_type == "PROPOSAL":
        token = gpu_model.upper().replace(" ", "")
        names = [n for n in base.text_names() if "Proposal" in n and any(t in n.upper() for t in ("B300", "B200", "H200")) and
                 any(t in n.upper() for t in ("B300", "B200", "H200") if t in token)]
        names = names or [n for n in base.text_names() if "Proposal" in n][:2]
        refs += [(n, base.text(n, 5500)) for n in names[:2]]
    else:
        refs.append(("TensorBay MSA standard form", base.text("TensorBay_MSA_Standard_Form")))
    return refs


def build_document(
    ctx: dict[str, Any], doc_type: str, notes: str | None,
    base: kb.KnowledgeBase, svc: BedrockDocumentService,
) -> tuple[bytes, str | None]:
    """Blocking. Returns (docx bytes, markdown or None for filled forms)."""
    opp = ctx["opportunity"]
    if doc_type in FILLED_FORMS:
        template = base.template(doc_type)
        spec_line: str | None = None
        if doc_type == "MSA":
            specs = _spec_names(base, opp["gpu_model"])
            if specs:
                try:
                    spec_line = svc.complete(prompts.SPEC_LINE_PROMPT, base.text(specs[0], 6000), max_tokens=400).strip().splitlines()[0]
                except Exception as exc:  # noqa: BLE001 - the form is still usable with the blank
                    logger.warning("msa_spec_line_failed", error=str(exc))
            return forms.fill_msa(template, ctx, spec_line, notes), None
        return forms.fill_nda(template, ctx, notes), None

    kind = {"PROPOSAL": "PROP", "ORDER_FORM": "OF", "POC_AGREEMENT": "POC", "ESCROW_AGREEMENT": "ESC",
            "ACCEPTANCE_NOTICE": "ACC", "LOI": "LOI", "CONTRACT": "CON"}.get(doc_type, doc_type)
    ctx = {**ctx, "reference": ctx["reference"].format(kind=kind)}
    deal_json = json.dumps(ctx, indent=1, ensure_ascii=False, default=str)
    user = prompts.user_prompt(doc_type, deal_json, _references(base, doc_type, opp["gpu_model"]), notes)
    markdown = svc.complete(prompts.SYSTEM_PROMPT, user, max_tokens=svc.settings.bedrock_max_tokens)
    title = f"{TYPE_TITLE.get(doc_type, doc_type)} - {ctx['customer']['legal_name']}"
    return render.markdown_to_docx(markdown, title), markdown


async def save_to_drive(session: AsyncSession, settings: Settings, doc: GeneratedDocument, data: bytes, actor: str) -> None:
    """File the DOCX in Drive; failures are recorded on the document, never raised."""
    doc.drive_error = None
    conn = None
    try:
        opp, customer, _contacts, _quote = await deal.load_deal(session, doc.opportunity_id)  # type: ignore[arg-type]
        conn = await drive_service.get_connection(session)
        drive = drive_service.make_drive(settings, conn)
        if conn is None or drive is None:
            doc.drive_error = "Google Drive is not connected. Connect it on the Documents page, then use Save to Drive."
            return
        folder = drive_service.opportunity_folder_name(opp.created_at, opp.short_name, opp.gpu_model, opp.quantity)
        parts = drive_service.document_path(customer.legal_name, folder, TYPE_FOLDER[doc.doc_type.value])
        item = await drive_service.save_file(session, drive, conn, parts, doc.file_name or "document.docx", data, DOCX_MIME, actor)
        doc.drive_file_id, doc.drive_url = item.id, item.url
    except DriveError as exc:
        doc.drive_error = str(exc)
    except Exception as exc:  # noqa: BLE001
        if drive_service.is_revoked(exc):
            if conn is not None:
                conn.needs_reconnect = True
            doc.drive_error = "Google access was revoked or expired. Reconnect Google Drive, then use Save to Drive."
        else:
            logger.warning("drive_save_failed", error=str(exc))
            doc.drive_error = f"Could not save to Google Drive: {drive_service_message(exc)}"


def drive_service_message(exc: Exception) -> str:
    from neocloud.domains.drive.router import _google_message

    return _google_message(exc)


async def run_generation(document_id: str) -> None:
    """Background job: build the file, store it, file it in Drive, update the row."""
    settings = get_settings()
    async with get_sessionmaker()() as session:
        doc = await session.get(GeneratedDocument, document_id)
        if doc is None or doc.opportunity_id is None:
            return
        try:
            opp, customer, contacts, quote = await deal.load_deal(session, doc.opportunity_id)
            ctx = deal.build_context(opp, customer, contacts, quote)
            svc = BedrockDocumentService(settings)
            data, markdown = await asyncio.to_thread(
                build_document, ctx, doc.doc_type.value, doc.notes, kb.get_kb(), svc
            )
            if settings.documents_bucket:
                base_key = f"documents/{doc.doc_type.value}/{doc.opportunity_id}/v{doc.version}-{doc.id}"
                doc.docx_s3_key = f"{base_key}.docx"
                await asyncio.to_thread(
                    svc._put_object, Bucket=settings.documents_bucket, Key=doc.docx_s3_key, Body=data, ContentType=DOCX_MIME
                )
                if markdown:
                    doc.s3_key = f"{base_key}.md"
                    await asyncio.to_thread(
                        svc._put_object, Bucket=settings.documents_bucket, Key=doc.s3_key,
                        Body=markdown.encode(), ContentType="text/markdown; charset=utf-8",
                    )
            doc.status = DocumentStatus.GENERATED
            doc.error = None
            await save_to_drive(session, settings, doc, data, doc.created_by or "system")
        except (kb.KbMissing, LookupError) as exc:
            doc.status, doc.error = DocumentStatus.FAILED, str(exc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("document_generation_failed", document_id=document_id)
            doc.status, doc.error = DocumentStatus.FAILED, f"{type(exc).__name__}: {exc}"[:1000]
        await session.commit()


async def next_version(session: AsyncSession, opportunity_id: str, doc_type: DocType) -> int:
    rows = (
        await session.execute(
            select(GeneratedDocument.version).where(
                GeneratedDocument.opportunity_id == opportunity_id, GeneratedDocument.doc_type == doc_type
            )
        )
    ).scalars().all()
    return (max(rows) if rows else 0) + 1
