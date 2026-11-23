"""TensorBay knowledge base: the standard forms and reference documents.

The files live in the private documents bucket under ``kb/`` (uploaded by
``scripts/ingest_kb.py``). Standard forms (``kb/templates/*.docx``) are filled in,
never rewritten by AI; the plain-text references (``kb/text/*.txt``) ground the
AI-written documents. Everything is cached in memory for the life of the process.
"""

from functools import lru_cache

import boto3

from neocloud.core.config import Settings, get_settings

TEMPLATE_PREFIX = "kb/templates/"
TEXT_PREFIX = "kb/text/"


class KbMissing(RuntimeError):
    pass


class KnowledgeBase:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._cache: dict[str, bytes] = {}
        self._names: list[str] | None = None

    def _s3(self):
        return boto3.client("s3", region_name=self.settings.aws_region)

    def _get(self, key: str) -> bytes:
        if key not in self._cache:
            bucket = self.settings.documents_bucket
            if not bucket:
                raise KbMissing("The documents bucket is not configured.")
            try:
                self._cache[key] = self._s3().get_object(Bucket=bucket, Key=key)["Body"].read()
            except Exception as exc:  # noqa: BLE001
                raise KbMissing(f"Knowledge base file {key} could not be read ({type(exc).__name__}).") from exc
        return self._cache[key]

    def template(self, name: str) -> bytes:
        """A standard DOCX form: ``MSA``, ``NDA`` or ``REFERRAL``."""
        return self._get(f"{TEMPLATE_PREFIX}{name}.docx")

    def text_names(self) -> list[str]:
        if self._names is None:
            bucket = self.settings.documents_bucket
            if not bucket:
                raise KbMissing("The documents bucket is not configured.")
            keys: list[str] = []
            for page in self._s3().get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=TEXT_PREFIX):
                keys += [o["Key"][len(TEXT_PREFIX):-4] for o in page.get("Contents", []) if o["Key"].endswith(".txt")]
            self._names = sorted(keys)
        return self._names

    def text(self, name: str, limit: int | None = None) -> str:
        body = self._get(f"{TEXT_PREFIX}{name}.txt").decode("utf-8", errors="replace")
        return body[:limit] if limit else body

    def find(self, *needles: str) -> list[str]:
        """Names of reference texts containing every needle (case-insensitive)."""
        low = [n.lower() for n in needles]
        return [n for n in self.text_names() if all(x in n.lower() for x in low)]


@lru_cache
def get_kb() -> KnowledgeBase:
    return KnowledgeBase()
