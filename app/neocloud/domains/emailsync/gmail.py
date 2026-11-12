"""Thin async wrapper over the Gmail API using a delegated service account.

The Google client is blocking, so every call runs in a worker thread. The
service account impersonates exactly one mailbox per reader (``subject``), and
only ever with the read-only scope.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Protocol

import boto3

from neocloud.core.config import Settings
from neocloud.core.logging import get_logger

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SKIP_LABELS = {"SPAM", "TRASH", "DRAFT"}
OPT_OUT_LABEL = "nocrm"  # a seller can label a thread "NoCRM" to keep it out

_sa_cache: tuple[float, dict | None] | None = None
_SA_TTL = 300


class HistoryExpired(Exception):
    """Gmail no longer has history from our cursor; do a fresh lookback."""


class MailReader(Protocol):
    async def current_history_id(self) -> str: ...
    async def list_recent(self, lookback_days: int, limit: int) -> list[str]: ...
    async def history_added(self, start_history_id: str) -> tuple[list[str], str]: ...
    async def get_message(self, message_id: str) -> dict | None: ...


def load_service_account(settings: Settings) -> dict | None:
    """The service-account key as a dict, or None when not configured."""
    global _sa_cache
    raw: str | None = settings.gmail_sa_json
    if not raw and settings.gmail_sa_secret_arn:
        now = time.monotonic()
        if _sa_cache and now - _sa_cache[0] < _SA_TTL:
            return _sa_cache[1]
        try:
            client = boto3.client("secretsmanager", region_name=settings.aws_region)
            raw = client.get_secret_value(SecretId=settings.gmail_sa_secret_arn)["SecretString"]
        except Exception as exc:  # noqa: BLE001
            logger.error("gmail_sa_secret_fetch_failed", error=str(exc))
            return None
    info: dict | None = None
    try:
        parsed = json.loads(raw or "{}")
        if isinstance(parsed, dict) and parsed.get("private_key") and parsed.get("client_email"):
            info = parsed
    except json.JSONDecodeError:
        info = None
    if settings.gmail_sa_secret_arn and not settings.gmail_sa_json:
        _sa_cache = (time.monotonic(), info)
    return info


class GmailReader:
    def __init__(self, sa_info: dict, mailbox: str):
        self._sa_info = sa_info
        self._mailbox = mailbox
        self._service = None
        self._skip_ids: set[str] | None = None

    def _svc(self):  # noqa: ANN202
        if self._service is None:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds = service_account.Credentials.from_service_account_info(
                self._sa_info, scopes=SCOPES, subject=self._mailbox
            )
            self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def _skip_label_ids(self) -> set[str]:
        if self._skip_ids is None:
            ids = set(SKIP_LABELS)
            labels = self._svc().users().labels().list(userId="me").execute().get("labels", [])
            ids.update(l["id"] for l in labels if l.get("name", "").lower() == OPT_OUT_LABEL)
            self._skip_ids = ids
        return self._skip_ids

    # ---- blocking implementations (run in a thread) ----------------------- #
    def _profile(self) -> str:
        return str(self._svc().users().getProfile(userId="me").execute()["historyId"])

    def _list_recent(self, lookback_days: int, limit: int) -> list[str]:
        q = f"newer_than:{lookback_days}d -in:spam -in:trash -in:drafts -label:{OPT_OUT_LABEL}"
        ids: list[str] = []
        req = self._svc().users().messages().list(userId="me", q=q, maxResults=min(limit, 100))
        while req is not None and len(ids) < limit:
            resp = req.execute()
            ids.extend(m["id"] for m in resp.get("messages", []))
            req = self._svc().users().messages().list_next(req, resp)
        return ids[:limit]

    def _history_added(self, start: str) -> tuple[list[str], str]:
        from googleapiclient.errors import HttpError

        ids: dict[str, None] = {}
        newest = start
        token = None
        try:
            while True:
                resp = (
                    self._svc()
                    .users()
                    .history()
                    .list(
                        userId="me",
                        startHistoryId=start,
                        historyTypes=["messageAdded"],
                        pageToken=token,
                    )
                    .execute()
                )
                for h in resp.get("history", []):
                    for added in h.get("messagesAdded", []):
                        ids.setdefault(added["message"]["id"], None)
                newest = str(resp.get("historyId", newest))
                token = resp.get("nextPageToken")
                if not token:
                    break
        except HttpError as exc:
            if getattr(exc.resp, "status", None) == 404:
                raise HistoryExpired() from exc
            raise
        return list(ids), newest

    def _get(self, message_id: str) -> dict | None:
        from googleapiclient.errors import HttpError

        try:
            msg = (
                self._svc().users().messages().get(userId="me", id=message_id, format="full").execute()
            )
        except HttpError as exc:
            if getattr(exc.resp, "status", None) == 404:  # deleted since listing
                return None
            raise
        if self._skip_label_ids() & set(msg.get("labelIds") or []):
            return None
        return msg

    # ---- async facade ------------------------------------------------------ #
    async def current_history_id(self) -> str:
        return await asyncio.to_thread(self._profile)

    async def list_recent(self, lookback_days: int, limit: int) -> list[str]:
        return await asyncio.to_thread(self._list_recent, lookback_days, limit)

    async def history_added(self, start_history_id: str) -> tuple[list[str], str]:
        return await asyncio.to_thread(self._history_added, start_history_id)

    async def get_message(self, message_id: str) -> dict | None:
        return await asyncio.to_thread(self._get, message_id)
