"""Google Drive storage: connect via the shared Google callback, choose the root
folder, build Clients/<customer>/<deal>/<type>/ and file documents."""

import json
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from neocloud.core.config import Settings, get_settings
from neocloud.domains.drive import service
from neocloud.domains.drive.models import DriveFolder
from neocloud.domains.drive.service import DriveItem
from neocloud.domains.emailsync import oauth

V1 = "/v1"
KEY = Fernet.generate_key().decode()


class FakeDrive:
    """In-memory Drive: folders by id, with parent links."""

    def __init__(self):
        self.items: dict[str, dict] = {
            "ROOTFOLDER123": {"name": "CRM TensorBay", "parent": None, "folder": True, "write": True},
            "READONLY12345": {"name": "Só leitura", "parent": None, "folder": True, "write": False},
        }
        self.uploads: list[tuple[str, str, bytes]] = []
        self.revoked = False
        self._n = 0

    def _id(self) -> str:
        self._n += 1
        return f"F{self._n:010d}"

    def _raise_if_revoked(self):
        if self.revoked:
            raise Exception("('invalid_grant: Token has been expired or revoked.', {})")

    async def get_folder(self, folder_id):
        self._raise_if_revoked()
        it = self.items.get(folder_id)
        if not it or not it["folder"]:
            return None
        return DriveItem(folder_id, it["name"], f"https://drive.google.com/drive/folders/{folder_id}", it["write"])

    async def search_folders(self, name):
        self._raise_if_revoked()
        return [DriveItem(k, v["name"], None, v["write"]) for k, v in self.items.items()
                if v["folder"] and name.lower() in v["name"].lower()]

    async def find_child_folder(self, parent_id, name):
        for k, v in self.items.items():
            if v["folder"] and v["parent"] == parent_id and v["name"] == name:
                return DriveItem(k, name, None)
        return None

    async def create_folder(self, parent_id, name):
        fid = self._id()
        self.items[fid] = {"name": name, "parent": parent_id, "folder": True, "write": True}
        return DriveItem(fid, name, None)

    async def find_file(self, parent_id, name):
        for k, v in self.items.items():
            if not v["folder"] and v["parent"] == parent_id and v["name"] == name:
                return DriveItem(k, name, None)
        return None

    async def upload(self, parent_id, name, content, mime):
        fid = self._id()
        self.items[fid] = {"name": name, "parent": parent_id, "folder": False, "write": True}
        self.uploads.append((parent_id, name, content))
        return DriveItem(fid, name, f"https://drive.google.com/file/d/{fid}/view")

    def path_of(self, fid: str) -> str:
        parts = []
        while fid:
            parts.append(self.items[fid]["name"])
            fid = self.items[fid]["parent"]
        return "/".join(reversed(parts))


@pytest.fixture
def env(monkeypatch):
    from neocloud.main import app

    st = Settings(
        gmail_oauth_json=json.dumps({"client_id": "cid", "client_secret": "sec"}),
        gmail_token_key=KEY, app_base_url="https://dev.crm.tensorbay.io",
    )
    app.dependency_overrides[get_settings] = lambda: st
    fake = FakeDrive()
    box = {"email": "crm@tensorbay.io", "revokes": []}

    async def fake_exchange(settings, code, required_scope=oauth.GMAIL_SCOPE):
        if code == "no-drive":
            raise oauth.OAuthError("Access to Google Drive was not granted. Approve every permission requested.")
        return oauth.ExchangeResult(refresh_token=f"rt-{required_scope.rsplit('/', 1)[-1]}", email=box["email"])

    async def fake_revoke(token):
        box["revokes"].append(token)

    monkeypatch.setattr(oauth, "exchange_code", fake_exchange)
    monkeypatch.setattr(oauth, "revoke_token", fake_revoke)
    monkeypatch.setattr(service, "make_drive", lambda s, c: fake if c and c.refresh_token_enc and not c.needs_reconnect else None)
    yield st, fake, box
    app.dependency_overrides.pop(get_settings, None)


async def _connect(client) -> dict:
    url = (await client.post(f"{V1}/drive/connect")).json()["authorization_url"]
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    assert q["login_hint"] == "crm@tensorbay.io"
    assert q["scope"].split() == ["openid", "email", "https://www.googleapis.com/auth/drive"]
    assert q["redirect_uri"] == "https://dev.crm.tensorbay.io/email/oauth/callback"
    r = await client.post(f"{V1}/email-sync/oauth/callback", json={"code": "good", "state": q["state"]})
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------------- #
def test_folder_links_and_names() -> None:
    fid = "1AbCdEfGhIjKlMnOpQrStUvWxYz012345"
    assert service.folder_id_from(f"https://drive.google.com/drive/folders/{fid}?usp=sharing") == fid
    assert service.folder_id_from(f"https://drive.google.com/drive/u/1/folders/{fid}") == fid
    assert service.folder_id_from(f"https://drive.google.com/open?id={fid}") == fid
    assert service.folder_id_from(fid) == fid
    with pytest.raises(service.DriveError):
        service.folder_id_from("not a link")
    assert service.safe_name("Foxgaroo / B300\n 64 nodes ") == "Foxgaroo - B300 64 nodes"
    assert service.safe_name("   ") == "Untitled"
    assert service.document_path("Akash", None, "MSA") == ["Clients", "Akash", "MSA"]


async def test_connect_through_shared_callback_choose_root_and_check(client, env) -> None:
    st, fake, _ = env
    body = await _connect(client)
    assert body["kind"] == "drive" and body["connected"] and body["account_email"] == "crm@tensorbay.io"
    status = (await client.get(f"{V1}/drive/status")).json()
    assert status["connected"] and status["root_folder_id"] is None

    found = (await client.get(f"{V1}/drive/folders", params={"name": "crm"})).json()
    assert [f["name"] for f in found] == ["CRM TensorBay"] and found[0]["can_write"]

    r = await client.put(f"{V1}/drive/root", json={"folder": "https://drive.google.com/drive/folders/ROOTFOLDER123"})
    assert r.status_code == 200 and r.json()["root_folder_name"] == "CRM TensorBay"
    chk = await client.post(f"{V1}/drive/check")
    assert chk.status_code == 200 and chk.json()["folder_path"] == "CRM TensorBay/Clients"
    parent, name, _ = fake.uploads[-1]
    assert fake.path_of(parent) == "CRM TensorBay/Clients" and name == "README (portal).txt"
    # Running the check again neither duplicates the folder nor the note.
    assert (await client.post(f"{V1}/drive/check")).status_code == 200
    assert len(fake.uploads) == 1
    assert len([v for v in fake.items.values() if v["folder"] and v["name"] == "Clients"]) == 1


async def test_root_must_be_visible_and_writable(client, env) -> None:
    await _connect(client)
    assert (await client.put(f"{V1}/drive/root", json={"folder": "MISSINGFOLDER1"})).status_code == 404
    assert (await client.put(f"{V1}/drive/root", json={"folder": "READONLY12345"})).status_code == 403
    assert (await client.put(f"{V1}/drive/root", json={"folder": "not a folder link"})).status_code == 422
    assert (await client.post(f"{V1}/drive/check")).status_code == 409  # no root yet


async def test_document_tree_is_created_once_and_heals(session, env) -> None:
    st, fake, _ = env
    parts = service.document_path("Foxgaroo", "GB200 216 GPUs", "Order Form")
    a = await service.ensure_path(session, fake, "ROOTFOLDER123", parts, "t")
    b = await service.ensure_path(session, fake, "ROOTFOLDER123", parts, "t")
    assert a == b and fake.path_of(a) == "CRM TensorBay/Clients/Foxgaroo/GB200 216 GPUs/Order Form"
    folders = [v for v in fake.items.values() if v["folder"]]
    assert len(folders) == 2 + 4  # two pre-existing + 4 created, no duplicates
    # A sibling type reuses the customer and deal folders.
    c = await service.ensure_path(session, fake, "ROOTFOLDER123", service.document_path("Foxgaroo", "GB200 216 GPUs", "MSA"), "t")
    assert fake.path_of(c).endswith("GB200 216 GPUs/MSA") and len([v for v in fake.items.values() if v["folder"]]) == 7
    # Someone deletes the customer folder in Drive: it is re-created on next save.
    cust = (await session.execute(select(DriveFolder).where(DriveFolder.path == "/Clients/Foxgaroo"))).scalars().first()
    del fake.items[cust.folder_id]
    d = await service.ensure_path(session, fake, "ROOTFOLDER123", parts, "t")
    assert d != a and fake.path_of(d) == "CRM TensorBay/Clients/Foxgaroo/GB200 216 GPUs/Order Form"


async def test_revoked_access_is_flagged_not_500(client, env) -> None:
    st, fake, _ = env
    await _connect(client)
    await client.put(f"{V1}/drive/root", json={"folder": "ROOTFOLDER123"})
    fake.revoked = True
    r = await client.get(f"{V1}/drive/folders")
    assert r.status_code == 409 and "Reconnect" in r.json()["detail"]
    assert (await client.get(f"{V1}/drive/status")).json()["needs_reconnect"] is True
    fake.revoked = False
    await _connect(client)  # reconnecting clears the flag and keeps the root
    s = (await client.get(f"{V1}/drive/status")).json()
    assert not s["needs_reconnect"] and s["root_folder_id"] == "ROOTFOLDER123"


async def test_missing_drive_permission_is_a_clear_error(client, env) -> None:
    url = (await client.post(f"{V1}/drive/connect")).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    r = await client.post(f"{V1}/email-sync/oauth/callback", json={"code": "no-drive", "state": state})
    assert r.status_code == 400 and "Google Drive" in r.json()["detail"]


async def test_disconnects_never_cut_the_other_connection(client, env) -> None:
    """crm@ powers both the Gmail sync and Drive: revoking at Google would kill both."""
    st, fake, box = env
    await _connect(client)
    mb = (await client.post(f"{V1}/email-sync/mailboxes", json={"address": "crm@tensorbay.io", "capture_unmatched": True})).json()
    url = (await client.post(f"{V1}/email-sync/mailboxes/{mb['id']}/connect")).json()["authorization_url"]
    r = await client.post(f"{V1}/email-sync/oauth/callback", json={"code": "good", "state": parse_qs(urlparse(url).query)["state"][0]})
    assert r.status_code == 200 and r.json()["kind"] == "mailbox" and r.json()["connected"]

    # Disconnecting the mailbox keeps the Google grant because Drive uses it.
    assert (await client.post(f"{V1}/email-sync/mailboxes/{mb['id']}/disconnect")).status_code == 200
    assert box["revokes"] == []
    # Disconnecting Drive never revokes.
    assert (await client.post(f"{V1}/drive/disconnect")).json()["connected"] is False
    assert box["revokes"] == []


async def test_only_admins_manage_drive(client, env) -> None:
    from neocloud.auth.dependencies import CurrentUser, get_current_user
    from neocloud.auth.rbac import permissions_for_roles
    from neocloud.main import app

    roles = ["SALES_MANAGER"]
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        subject="m", email=None, roles=roles, permissions=permissions_for_roles(roles))
    try:
        assert (await client.post(f"{V1}/drive/connect")).status_code == 403
        assert (await client.put(f"{V1}/drive/root", json={"folder": "ROOTFOLDER123"})).status_code == 403
        assert (await client.post(f"{V1}/drive/check")).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_google_errors_are_shown_in_plain_words() -> None:
    from neocloud.domains.drive.router import _google_message

    class HttpErr(Exception):
        content = b'{"error": {"code": 403, "message": "Google Drive API has not been used in project 1 before or it is disabled."}}'

    assert _google_message(HttpErr("<HttpError 403 when requesting https://...>")).startswith("Google Drive API has not been used")
    assert _google_message(ValueError("boom")) == "boom"


def test_opportunity_folder_is_year_month_short_name() -> None:
    from datetime import date, datetime

    assert service.opportunity_folder_name(datetime(2026, 11, 21, 15, 0), "Foxgaroo GB200", "GB200", 216) == "2026-11-Foxgaroo GB200"
    assert service.opportunity_folder_name(date(2027, 1, 5), None, "B300", 512) == "2027-01-B300-512"
    assert service.opportunity_folder_name(date(2027, 1, 5), "  ", "B300", 512) == "2027-01-B300-512"
    assert service.opportunity_folder_name(date(2026, 3, 1), "Akash / phase 2", "H200", 8) == "2026-03-Akash - phase 2"
    parts = service.document_path("Foxgaroo", service.opportunity_folder_name(date(2026, 11, 1), "GB200 216", "GB200", 216), "Order Form")
    assert parts == ["Clients", "Foxgaroo", "2026-11-GB200 216", "Order Form"]


async def test_opportunity_short_name_round_trip(client) -> None:
    cid = (await client.post(f"{V1}/customers", json={"legal_name": "Short Co", "status": "PROSPECT"})).json()["id"]
    body = {"customer_id": cid, "gpu_model": "B300", "quantity": 64, "duration_months": 12,
            "commercial_model": "GPU_MONTHLY", "expected_mrr": "1000", "short_name": "Short B300"}
    o = (await client.post(f"{V1}/sales/opportunities", json=body)).json()
    assert o["short_name"] == "Short B300"
    o = (await client.patch(f"{V1}/sales/opportunities/{o['id']}", json={"short_name": "Renamed"})).json()
    assert o["short_name"] == "Renamed"
    too_long = await client.post(f"{V1}/sales/opportunities", json={**body, "short_name": "x" * 61})
    assert too_long.status_code == 422
