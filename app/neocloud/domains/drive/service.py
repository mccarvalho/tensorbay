"""Google Drive client + the folder tree for generated documents."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.core.config import Settings
from neocloud.core.logging import get_logger
from neocloud.domains.drive.models import DriveConnection, DriveFolder
from neocloud.domains.emailsync import oauth

logger = get_logger(__name__)

FOLDER_MIME = "application/vnd.google-apps.folder"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
CLIENTS_FOLDER = "Clients"
README_NAME = "README (portal).txt"
_FIELDS = "id,name,mimeType,webViewLink,capabilities(canAddChildren),trashed"
_ID_IN_URL = re.compile(r"(?:folders/|id=)([A-Za-z0-9_-]{10,})")


class DriveError(Exception):
    """A user-presentable Drive problem."""


@dataclass
class DriveItem:
    id: str
    name: str
    url: str | None
    can_add_children: bool = True


class DriveApi(Protocol):
    async def get_folder(self, folder_id: str) -> DriveItem | None: ...
    async def search_folders(self, name: str) -> list[DriveItem]: ...
    async def find_child_folder(self, parent_id: str, name: str) -> DriveItem | None: ...
    async def create_folder(self, parent_id: str, name: str) -> DriveItem: ...
    async def upload(self, parent_id: str, name: str, content: bytes, mime: str) -> DriveItem: ...
    async def find_file(self, parent_id: str, name: str) -> DriveItem | None: ...


def folder_id_from(value: str) -> str:
    """Accept a Drive folder URL or a bare folder id."""
    value = value.strip()
    m = _ID_IN_URL.search(value)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{10,}", value):
        return value
    raise DriveError("That doesn't look like a Google Drive folder link or id.")


def safe_name(name: str, limit: int = 120) -> str:
    """A folder/file name Drive and people both handle well."""
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", " ", name or "")  # line breaks, tabs -> space
    cleaned = re.sub(r"\s*[\\/]+\s*", " - ", cleaned)  # path separators -> " - "
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-")
    return (cleaned or "Untitled")[:limit]


def _q(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


class GoogleDrive:
    """Thin async wrapper over Drive v3 (blocking client run in a thread)."""

    def __init__(self, credentials: Any):
        self._credentials = credentials
        self._service = None

    def _svc(self):  # noqa: ANN202
        if self._service is None:
            from googleapiclient.discovery import build

            self._service = build("drive", "v3", credentials=self._credentials, cache_discovery=False)
        return self._service

    @staticmethod
    def _item(f: dict) -> DriveItem:
        return DriveItem(
            id=f["id"], name=f.get("name", ""), url=f.get("webViewLink"),
            can_add_children=bool((f.get("capabilities") or {}).get("canAddChildren", True)),
        )

    def _get(self, folder_id: str) -> DriveItem | None:
        from googleapiclient.errors import HttpError

        try:
            f = self._svc().files().get(fileId=folder_id, fields=_FIELDS, supportsAllDrives=True).execute()
        except HttpError as exc:
            if getattr(exc.resp, "status", None) in (403, 404):
                return None
            raise
        if f.get("trashed") or f.get("mimeType") != FOLDER_MIME:
            return None
        return self._item(f)

    def _list(self, q: str, page_size: int = 25) -> list[DriveItem]:
        resp = self._svc().files().list(
            q=q, fields=f"files({_FIELDS})", pageSize=page_size, orderBy="name",
            supportsAllDrives=True, includeItemsFromAllDrives=True, corpora="allDrives",
        ).execute()
        return [self._item(f) for f in resp.get("files", [])]

    def _create_folder(self, parent_id: str, name: str) -> DriveItem:
        f = self._svc().files().create(
            body={"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]},
            fields=_FIELDS, supportsAllDrives=True,
        ).execute()
        return self._item(f)

    def _upload(self, parent_id: str, name: str, content: bytes, mime: str) -> DriveItem:
        from googleapiclient.http import MediaInMemoryUpload

        media = MediaInMemoryUpload(content, mimetype=mime, resumable=False)
        f = self._svc().files().create(
            body={"name": name, "parents": [parent_id]}, media_body=media,
            fields="id,name,webViewLink", supportsAllDrives=True,
        ).execute()
        return self._item(f)

    async def get_folder(self, folder_id: str) -> DriveItem | None:
        return await asyncio.to_thread(self._get, folder_id)

    async def search_folders(self, name: str) -> list[DriveItem]:
        q = f"mimeType = '{FOLDER_MIME}' and trashed = false"
        if name.strip():
            q += f" and name contains '{_q(name.strip())}'"
        return await asyncio.to_thread(self._list, q)

    async def find_child_folder(self, parent_id: str, name: str) -> DriveItem | None:
        q = (f"mimeType = '{FOLDER_MIME}' and trashed = false and "
             f"'{_q(parent_id)}' in parents and name = '{_q(name)}'")
        found = await asyncio.to_thread(self._list, q, 1)
        return found[0] if found else None

    async def create_folder(self, parent_id: str, name: str) -> DriveItem:
        return await asyncio.to_thread(self._create_folder, parent_id, name)

    async def find_file(self, parent_id: str, name: str) -> DriveItem | None:
        q = (f"mimeType != '{FOLDER_MIME}' and trashed = false and "
             f"'{_q(parent_id)}' in parents and name = '{_q(name)}'")
        found = await asyncio.to_thread(self._list, q, 1)
        return found[0] if found else None

    async def upload(self, parent_id: str, name: str, content: bytes, mime: str) -> DriveItem:
        return await asyncio.to_thread(self._upload, parent_id, name, content, mime)


# --------------------------------------------------------------------------- #
# Connection
# --------------------------------------------------------------------------- #
async def get_connection(session: AsyncSession) -> DriveConnection | None:
    return (await session.execute(select(DriveConnection).limit(1))).scalars().first()


def make_drive(settings: Settings, conn: DriveConnection | None) -> GoogleDrive | None:
    from google.oauth2.credentials import Credentials

    client = oauth.load_oauth_client(settings)
    if client is None or conn is None or not conn.refresh_token_enc or conn.needs_reconnect:
        return None
    refresh = oauth.decrypt_token(settings, conn.refresh_token_enc)
    if not refresh:
        return None
    creds = Credentials(
        token=None, refresh_token=refresh, client_id=client.client_id,
        client_secret=client.client_secret, token_uri=oauth.TOKEN_URL, scopes=[oauth.DRIVE_SCOPE],
    )
    return GoogleDrive(creds)


def is_revoked(exc: Exception) -> bool:
    return type(exc).__name__ == "RefreshError" or "invalid_grant" in str(exc)


# --------------------------------------------------------------------------- #
# Folder tree
# --------------------------------------------------------------------------- #
async def ensure_path(
    session: AsyncSession, drive: DriveApi, root_id: str, parts: list[str], actor: str
) -> str:
    """Find or create ``root/parts[0]/parts[1]/...`` and return the last folder id.

    Folder ids are cached per path. A cached folder that was deleted or trashed in
    Drive is detected and re-created, so the tree heals itself.
    """
    parent = root_id
    path = ""
    trust_cache = True  # once a level is rebuilt, deeper cached ids are stale
    for raw in parts:
        name = safe_name(raw)
        path = f"{path}/{name}"
        cached = (
            await session.execute(
                select(DriveFolder).where(DriveFolder.root_folder_id == root_id, DriveFolder.path == path)
            )
        ).scalars().first()
        if trust_cache and cached and await drive.get_folder(cached.folder_id):
            parent = cached.folder_id
            continue
        trust_cache = False
        found = await drive.find_child_folder(parent, name) or await drive.create_folder(parent, name)
        if cached:
            cached.folder_id = found.id
            cached.updated_by = actor
        else:
            session.add(DriveFolder(root_folder_id=root_id, path=path, folder_id=found.id,
                                    created_by=actor, updated_by=actor))
        await session.flush()
        parent = found.id
    return parent


def document_path(customer: str, deal: str | None, doc_type: str) -> list[str]:
    """``Clients/<customer>/<deal>/<doc type>`` (deal folder skipped if unknown)."""
    parts = [CLIENTS_FOLDER, customer]
    if deal:
        parts.append(deal)
    parts.append(doc_type)
    return parts


async def save_file(
    session: AsyncSession, drive: DriveApi, conn: DriveConnection, parts: list[str],
    filename: str, content: bytes, mime: str, actor: str,
) -> DriveItem:
    if not conn.root_folder_id:
        raise DriveError("Choose the root folder for documents first.")
    folder = await ensure_path(session, drive, conn.root_folder_id, parts, actor)
    return await drive.upload(folder, safe_name(filename, 200), content, mime)
