"""Thin async wrapper over the Gmail API using a mailbox owner's OAuth grant.

The Google client is blocking, so every call runs in a worker thread. A reader
holds one mailbox's credentials and only ever has the read-only Gmail scope.
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from neocloud.core.config import Settings
from neocloud.core.logging import get_logger
from neocloud.domains.emailsync import oauth

logger = get_logger(__name__)

SKIP_LABELS = {"SPAM", "TRASH", "DRAFT"}
OPT_OUT_LABEL = "nocrm"  # a seller can label a thread "NoCRM" to keep it out


class HistoryExpired(Exception):
    """Gmail no longer has history from our cursor; do a fresh lookback."""


class MailReader(Protocol):
    async def current_history_id(self) -> str: ...
    async def list_recent(self, lookback_days: int, limit: int) -> list[str]: ...
    async def history_added(self, start_history_id: str) -> tuple[list[str], str]: ...
    async def get_message(self, message_id: str) -> dict | None: ...


def make_reader(settings: Settings, mailbox) -> "GmailReader | None":  # noqa: ANN001
    """A reader for a connected mailbox, or None if it can't be built (not
    connected, or the OAuth client / encryption key isn't configured)."""
    from google.oauth2.credentials import Credentials

    client = oauth.load_oauth_client(settings)
    if client is None or not mailbox.refresh_token_enc or mailbox.needs_reconnect:
        return None
    refresh = oauth.decrypt_token(settings, mailbox.refresh_token_enc)
    if not refresh:
        return None
    creds = Credentials(
        token=None,
        refresh_token=refresh,
        client_id=client.client_id,
        client_secret=client.client_secret,
        token_uri=oauth.TOKEN_URL,
        scopes=[oauth.GMAIL_SCOPE],
    )
    return GmailReader(creds)


class GmailReader:
    def __init__(self, credentials):  # noqa: ANN001 - google.oauth2.credentials.Credentials
        self._credentials = credentials
        self._service = None
        self._skip_ids: set[str] | None = None

    def _svc(self):  # noqa: ANN202
        if self._service is None:
            from googleapiclient.discovery import build

            self._service = build(
                "gmail", "v1", credentials=self._credentials, cache_discovery=False
            )
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
