"""Google Drive connection for generated documents (Super Admin)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.core.config import Settings, get_settings
from neocloud.db.session import get_session
from neocloud.domains.drive import service
from neocloud.domains.drive.models import DriveConnection
from neocloud.domains.emailsync import oauth

router = APIRouter(prefix="/drive", tags=["Google Drive"])

Session = Annotated[AsyncSession, Depends(get_session)]
Admin = Annotated[CurrentUser, Depends(require_permission(Permission.USER_ADMIN))]
DocUser = Annotated[CurrentUser, Depends(require_permission(Permission.DOCUMENT_GENERATE))]
Cfg = Annotated[Settings, Depends(get_settings)]
DEFAULT_ACCOUNT = "crm@tensorbay.io"


class DriveStatus(BaseModel):
    configured: bool
    connected: bool
    account_email: str | None = None
    connected_at: datetime | None = None
    connected_by: str | None = None
    needs_reconnect: bool = False
    last_error: str | None = None
    root_folder_id: str | None = None
    root_folder_name: str | None = None
    root_folder_url: str | None = None
    redirect_uri: str


class FolderOut(BaseModel):
    id: str
    name: str
    url: str | None
    can_write: bool


class RootIn(BaseModel):
    folder: str = Field(..., min_length=10, max_length=1024, description="Folder link or id")


class ConnectOut(BaseModel):
    authorization_url: str


class CheckOut(BaseModel):
    ok: bool
    file_url: str | None = None
    folder_path: str


def _status(settings: Settings, conn: DriveConnection | None) -> DriveStatus:
    return DriveStatus(
        configured=oauth.is_configured(settings),
        connected=bool(conn and conn.refresh_token_enc),
        account_email=conn.account_email if conn else None,
        connected_at=conn.connected_at if conn else None,
        connected_by=conn.connected_by if conn else None,
        needs_reconnect=bool(conn and conn.needs_reconnect),
        last_error=conn.last_error if conn else None,
        root_folder_id=conn.root_folder_id if conn else None,
        root_folder_name=conn.root_folder_name if conn else None,
        root_folder_url=conn.root_folder_url if conn else None,
        redirect_uri=oauth.redirect_uri(settings),
    )


async def _drive_or_409(session: AsyncSession, settings: Settings) -> tuple[DriveConnection, service.GoogleDrive]:
    conn = await service.get_connection(session)
    drive = service.make_drive(settings, conn)
    if conn is None or drive is None:
        raise HTTPException(status_code=409, detail="Google Drive is not connected. Connect it first.")
    return conn, drive


async def _call(session: AsyncSession, conn: DriveConnection, coro):  # noqa: ANN001, ANN202
    """Run a Drive call; a revoked grant flags the connection instead of a 500."""
    try:
        return await coro
    except service.DriveError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        if service.is_revoked(exc):
            conn.needs_reconnect = True
            conn.last_error = "Google access was revoked or expired. Reconnect Google Drive."
            await session.commit()
            raise HTTPException(status_code=409, detail=conn.last_error) from exc
        raise HTTPException(status_code=502, detail=f"Google Drive error: {str(exc)[:300]}") from exc


@router.get("/status", response_model=DriveStatus)
async def drive_status(session: Session, _user: DocUser, settings: Cfg):
    return _status(settings, await service.get_connection(session))


@router.post("/connect", response_model=ConnectOut)
async def start_connect(
    session: Session, user: Admin, settings: Cfg,
    account: Annotated[str, Query(max_length=320)] = DEFAULT_ACCOUNT,
):
    if not oauth.is_configured(settings):
        raise HTTPException(status_code=409, detail="Google OAuth is not configured yet")
    state = oauth.make_state(settings, account.strip().lower(), user.subject, kind=oauth.KIND_DRIVE)
    url = oauth.authorization_url(settings, account.strip().lower(), state, scopes=oauth.DRIVE_LOGIN_SCOPES)
    return ConnectOut(authorization_url=url)


async def complete_connect(
    session: AsyncSession, settings: Settings, user: CurrentUser, code: str
) -> DriveStatus:
    """Finish the OAuth round trip (called from the shared Google callback)."""
    result = await oauth.exchange_code(settings, code, required_scope=oauth.DRIVE_SCOPE)
    conn = await service.get_connection(session)
    if conn is None:
        conn = DriveConnection(account_email=result.email, created_by=user.subject)
        session.add(conn)
    elif conn.account_email != result.email:
        # A different account: its folders are different, start clean.
        conn.root_folder_id = conn.root_folder_name = conn.root_folder_url = None
    conn.account_email = result.email
    conn.refresh_token_enc = oauth.encrypt_token(settings, result.refresh_token)
    conn.connected_at = datetime.now(timezone.utc)
    conn.connected_by = user.email or user.subject
    conn.needs_reconnect = False
    conn.last_error = None
    conn.updated_by = user.subject
    await session.flush()
    await record_audit(session, action="connect", entity_type="drive", entity_id=conn.id,
                       actor=user.subject, new_value={"account": result.email})
    return _status(settings, conn)


@router.get("/folders", response_model=list[FolderOut])
async def search_folders(session: Session, _user: Admin, settings: Cfg,
                         name: Annotated[str, Query(max_length=200)] = ""):
    conn, drive = await _drive_or_409(session, settings)
    items = await _call(session, conn, drive.search_folders(name))
    return [FolderOut(id=i.id, name=i.name, url=i.url, can_write=i.can_add_children) for i in items]


@router.put("/root", response_model=DriveStatus)
async def set_root(payload: RootIn, session: Session, user: Admin, settings: Cfg):
    conn, drive = await _drive_or_409(session, settings)
    try:
        folder_id = service.folder_id_from(payload.folder)
    except service.DriveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    folder = await _call(session, conn, drive.get_folder(folder_id))
    if folder is None:
        raise HTTPException(
            status_code=404,
            detail=f"{conn.account_email} can't see that folder. Share it with this account as Editor.",
        )
    if not folder.can_add_children:
        raise HTTPException(status_code=403, detail=f"{conn.account_email} can only view that folder; it needs Editor access.")
    conn.root_folder_id, conn.root_folder_name, conn.root_folder_url = folder.id, folder.name, folder.url
    conn.updated_by = user.subject
    await session.flush()
    await record_audit(session, action="set_root", entity_type="drive", entity_id=conn.id,
                       actor=user.subject, new_value={"folder_id": folder.id, "name": folder.name})
    return _status(settings, conn)


@router.post("/check", response_model=CheckOut)
async def check_write(session: Session, user: Admin, settings: Cfg):
    """Prove the portal can file documents: create ``Clientes/`` and a small note in it."""
    conn, drive = await _drive_or_409(session, settings)
    if not conn.root_folder_id:
        raise HTTPException(status_code=409, detail="Choose the root folder first.")
    note = (
        "Esta pasta é mantida pelo portal TensorBay. Os documentos gerados são salvos em\n"
        "Clientes/<cliente>/<oportunidade ou contrato>/<tipo de documento>/.\n"
    ).encode()
    item = await _call(session, conn, service.save_file(
        session, drive, conn, [service.CLIENTS_FOLDER], "LEIA-ME (portal).txt", note, "text/plain", user.subject,
    ))
    await session.commit()
    return CheckOut(ok=True, file_url=item.url, folder_path=f"{conn.root_folder_name}/{service.CLIENTS_FOLDER}")


@router.post("/disconnect", response_model=DriveStatus)
async def disconnect(session: Session, user: Admin, settings: Cfg):
    """Forget the stored token. Google access is NOT revoked here on purpose: the
    same Google account and OAuth client also power the Gmail sync, and revoking
    would cut that too. Remove access in the Google account if really needed."""
    conn = await service.get_connection(session)
    if conn is None:
        raise HTTPException(status_code=404, detail="Google Drive is not connected")
    conn.refresh_token_enc = None
    conn.needs_reconnect = False
    conn.updated_by = user.subject
    await session.flush()
    await record_audit(session, action="disconnect", entity_type="drive", entity_id=conn.id, actor=user.subject)
    return _status(settings, conn)
