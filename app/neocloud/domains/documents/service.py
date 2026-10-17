"""Bedrock-backed document generation service.

Builds a prompt from a template plus structured context (customer, pricing,
commitment, SLA, term), invokes the Bedrock Converse API, optionally applies a
Bedrock Guardrail, and persists the rendered text to S3.

AWS interactions are isolated behind small instance methods
(``_bedrock_client``, ``_s3_client``, ``_converse``, ``_put_object``) so they
can be monkeypatched in tests without real AWS calls.
"""

import json
import uuid
from typing import Any

import boto3

from neocloud.core.config import Settings, get_settings
from neocloud.core.logging import get_logger

logger = get_logger(__name__)


DEFAULT_SYSTEM_PROMPT = (
    "You are a senior commercial counsel drafting GPU cloud agreements for "
    "NeoCloud. Produce clear, well-structured Markdown. Only use facts present "
    "in the provided context; do not invent clauses, prices, or legal terms. "
    "Flag any missing information explicitly as [TO BE COMPLETED]. This is a "
    "draft that will undergo human legal review."
)


class BedrockDocumentService:
    """Generates documents via Amazon Bedrock and stores them in S3."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    # --- AWS client factories (monkeypatch targets) -------------------------

    def _bedrock_client(self):
        return boto3.client(
            "bedrock-runtime", region_name=self.settings.aws_region
        )

    def _s3_client(self):
        return boto3.client("s3", region_name=self.settings.aws_region)

    # --- AWS call wrappers (monkeypatch targets) ----------------------------

    def _converse(self, **kwargs) -> dict[str, Any]:
        return self._bedrock_client().converse(**kwargs)

    def _put_object(self, **kwargs) -> dict[str, Any]:
        return self._s3_client().put_object(**kwargs)

    # --- Prompt construction ------------------------------------------------

    @staticmethod
    def build_prompt(doc_type: str, context: dict[str, Any], template_body: str) -> str:
        """Render the user prompt from the template plus structured context."""
        context_json = json.dumps(context, indent=2, default=str, ensure_ascii=False)
        return (
            f"Document type: {doc_type}\n\n"
            f"Template / instructions:\n{template_body}\n\n"
            f"Structured context (customer, pricing, commitment, SLA, term):\n"
            f"```json\n{context_json}\n```\n\n"
            "Generate the complete document in Markdown using the template and "
            "the structured context above."
        )

    # --- Public API ---------------------------------------------------------

    def generate(
        self,
        doc_type: str,
        context: dict[str, Any],
        template_body: str,
    ) -> tuple[str, str | None]:
        """Generate a document and persist it to S3.

        Returns a ``(text, s3_key)`` tuple. ``s3_key`` is ``None`` when no
        documents bucket is configured.
        """
        prompt = self.build_prompt(doc_type, context, template_body)

        converse_kwargs: dict[str, Any] = {
            "modelId": self.settings.bedrock_model_id,
            "system": [{"text": DEFAULT_SYSTEM_PROMPT}],
            "messages": [
                {"role": "user", "content": [{"text": prompt}]},
            ],
        }
        if self.settings.bedrock_guardrail_id:
            converse_kwargs["guardrailConfig"] = {
                "guardrailIdentifier": self.settings.bedrock_guardrail_id,
                "guardrailVersion": self.settings.bedrock_guardrail_version,
            }

        logger.info(
            "bedrock_generate_start",
            doc_type=doc_type,
            model_id=self.settings.bedrock_model_id,
            guardrail=bool(self.settings.bedrock_guardrail_id),
        )
        response = self._converse(**converse_kwargs)
        text = self._extract_text(response)

        s3_key = self._store(doc_type, text)
        logger.info(
            "bedrock_generate_done",
            doc_type=doc_type,
            chars=len(text),
            s3_key=s3_key,
        )
        return text, s3_key

    # --- Helpers ------------------------------------------------------------

    @staticmethod
    def _extract_text(response: dict[str, Any]) -> str:
        """Pull the concatenated text from a Converse API response."""
        message = response.get("output", {}).get("message", {})
        parts = [
            block["text"]
            for block in message.get("content", [])
            if isinstance(block, dict) and "text" in block
        ]
        return "\n".join(parts).strip()

    def _store(self, doc_type: str, text: str) -> str | None:
        bucket = self.settings.documents_bucket
        if not bucket:
            logger.info("documents_bucket_unset_skip_upload", doc_type=doc_type)
            return None

        s3_key = f"documents/{doc_type}/{uuid.uuid4()}.md"
        self._put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=text.encode("utf-8"),
            ContentType="text/markdown; charset=utf-8",
        )
        return s3_key
