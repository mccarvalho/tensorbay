"""Connecting a mailbox through Google OAuth (no service-account key)."""

import base64
import json
import time
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient
from sqlalchemy import select

from neocloud.auth.dependencies import CurrentUser, get_current_user
from neocloud.auth.rbac import permissions_for_roles
from neocloud.core.config import Settings, get_settings
from neocloud.domains.emailsync import oauth, service
from neocloud.domains.emailsync.gmail import GmailReader, make_reader
from neocloud.domains.emailsync.models import Mailbox
from tests.test_email_sync import FakeReader, gmail_msg

V1 = "/v1"
KEY = Fernet.generate_key().decode()
APP = "https://app.example.test"


def _settings(**kw) -> Settings:
    base = dict(
        gmail_oauth_json=json.dumps({"client_id": "cid.apps.googleusercontent.com", "client_secret": "csecret"}),
        gmail_token_key=KEY,
        app_base_url=APP,
    )
    base.update(kw)
    return Settings(**base)


@pytest.fixture
def configured():
    from neocloud.main import app

    st = _settings()
    app.dependency_overrides[get_settings] = lambda: st
    yield st
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture
def google(monkeypatch):
    """Fake Google: exchange_code returns whatever the test sets; revoke is recorded."""
    box = {"email": "crm@tensorbay.io", "refresh": "rt-super-secret", "revoked": []}

    async def fake_exchange(settings, code):
        if code == "bad":
            raise oauth.OAuthError("Google rejected the authorization code. Please try connecting again.")
        return oauth.ExchangeResult(refresh_token=box["refresh"], email=box["email"])

    async def fake_revoke(token):
        box["revoked"].append(token)

    monkeypatch.setattr(oauth, "exchange_code", fake_exchange)
    monkeypatch.setattr(oauth, "revoke_token", fake_revoke)
    return box


async def _mailbox(client: AsyncClient, address="crm@tensorbay.io") -> dict:
    r = await client.post(f"{V1}/email-sync/mailboxes", json={"address": address, "capture_unmatched": True})
    assert r.status_code == 201, r.text
    return r.json()


async def _state_for(client: AsyncClient, mb: dict) -> str:
    r = await client.post(f"{V1}/email-sync/mailboxes/{mb['id']}/connect")
    assert r.status_code == 200, r.text
    return parse_qs(urlparse(r.json()["authorization_url"]).query)["state"][0]


# --------------------------------------------------------------------------- #
# Crypto + state
# --------------------------------------------------------------------------- #
def test_unpadded_terraform_style_key_works_and_tokens_are_encrypted() -> None:
    raw = base64.urlsafe_b64encode(b"k" * 32).decode().rstrip("=")  # random_id.b64_url shape
    st = _settings(gmail_token_key=raw)
    blob = oauth.encrypt_token(st, "refresh-token")
    assert "refresh-token" not in blob and oauth.decrypt_token(st, blob) == "refresh-token"
    # A different key can't read it.
    assert oauth.decrypt_token(_settings(gmail_token_key=KEY), blob) is None


def test_state_is_bound_to_user_and_expires() -> None:
    st = _settings()
    state = oauth.make_state(st, "mb-1", "user-a")
    assert oauth.parse_state(st, state, "user-a") == "mb-1"
    with pytest.raises(oauth.OAuthError, match="different user"):
        oauth.parse_state(st, state, "user-b")
    with pytest.raises(oauth.OAuthError):
        oauth.parse_state(st, state[:-4] + "AAAA", "user-a")  # tampered
    old = Fernet(KEY.encode()).encrypt_at_time(json.dumps({"m": "mb-1", "u": "user-a"}).encode(), int(time.time()) - 3600)
    with pytest.raises(oauth.OAuthError, match="expired"):
        oauth.parse_state(st, base64.urlsafe_b64encode(old).decode(), "user-a")


def test_is_configured_needs_both_client_and_key() -> None:
    assert oauth.is_configured(_settings())
    assert not oauth.is_configured(_settings(gmail_oauth_json="{}"))
    assert not oauth.is_configured(_settings(gmail_token_key=None))


# --------------------------------------------------------------------------- #
# API flow
# --------------------------------------------------------------------------- #
async def test_connect_url_asks_for_offline_readonly_access(client, configured) -> None:
    st = (await client.get(f"{V1}/email-sync/status")).json()
    assert st["configured"] is True and st["redirect_uri"] == f"{APP}/email/oauth/callback"
    mb = await _mailbox(client)
    url = urlparse((await client.post(f"{V1}/email-sync/mailboxes/{mb['id']}/connect")).json()["authorization_url"])
    q = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert url.netloc == "accounts.google.com"
    assert q["client_id"] == "cid.apps.googleusercontent.com" and q["redirect_uri"] == f"{APP}/email/oauth/callback"
    assert q["access_type"] == "offline" and q["prompt"] == "consent" and q["login_hint"] == "crm@tensorbay.io"
    assert "https://www.googleapis.com/auth/gmail.readonly" in q["scope"].split()
    assert "gmail.modify" not in q["scope"] and "gmail.send" not in q["scope"]


async def test_connect_requires_configuration_and_a_real_mailbox(client) -> None:
    mb = await _mailbox(client)
    r = await client.post(f"{V1}/email-sync/mailboxes/{mb['id']}/connect")
    assert r.status_code == 409  # no OAuth client yet


async def test_connect_unknown_mailbox_404(client, configured) -> None:
    assert (await client.post(f"{V1}/email-sync/mailboxes/nope/connect")).status_code == 404


async def test_successful_connection_stores_only_an_encrypted_token(client, configured, google, session) -> None:
    mb = await _mailbox(client)
    state = await _state_for(client, mb)
    r = await client.post(f"{V1}/email-sync/oauth/callback", json={"code": "good", "state": state})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["connected"] is True and body["needs_reconnect"] is False and body["connected_at"]
    assert "refresh" not in json.dumps(body)  # token never leaves the server
    row = (await session.execute(select(Mailbox))).scalars().first()
    await session.refresh(row)
    assert row.refresh_token_enc and "rt-super-secret" not in row.refresh_token_enc
    assert oauth.decrypt_token(configured, row.refresh_token_enc) == "rt-super-secret"
    assert any(m["connected"] for m in (await client.get(f"{V1}/email-sync/status")).json()["mailboxes"])


async def test_signing_in_with_the_wrong_google_account_is_rejected(client, configured, google, session) -> None:
    mb = await _mailbox(client)
    google["email"] = "someone.else@gmail.com"
    state = await _state_for(client, mb)
    r = await client.post(f"{V1}/email-sync/oauth/callback", json={"code": "good", "state": state})
    assert r.status_code == 400 and "crm@tensorbay.io" in r.json()["detail"]
    assert google["revoked"] == ["rt-super-secret"]  # the wrong grant is revoked at once
    row = (await session.execute(select(Mailbox))).scalars().first()
    await session.refresh(row)
    assert row.refresh_token_enc is None


async def test_bad_code_bad_state_and_other_users_state_are_rejected(client, configured, google) -> None:
    from neocloud.main import app

    mb = await _mailbox(client)
    state = await _state_for(client, mb)
    assert (await client.post(f"{V1}/email-sync/oauth/callback", json={"code": "bad", "state": state})).status_code == 400
    assert (await client.post(f"{V1}/email-sync/oauth/callback", json={"code": "good", "state": "garbage"})).status_code == 400
    # Another admin can't finish a flow someone else started.
    roles = ["SUPER_ADMIN"]
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        subject="other-admin", email=None, roles=roles, permissions=permissions_for_roles(roles))
    try:
        r = await client.post(f"{V1}/email-sync/oauth/callback", json={"code": "good", "state": state})
        assert r.status_code == 400 and "different user" in r.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_disconnect_revokes_and_clears(client, configured, google, session) -> None:
    mb = await _mailbox(client)
    await client.post(f"{V1}/email-sync/oauth/callback", json={"code": "good", "state": await _state_for(client, mb)})
    r = await client.post(f"{V1}/email-sync/mailboxes/{mb['id']}/disconnect")
    assert r.status_code == 200 and r.json()["connected"] is False
    assert google["revoked"] == ["rt-super-secret"]
    row = (await session.execute(select(Mailbox))).scalars().first()
    await session.refresh(row)
    assert row.refresh_token_enc is None and row.history_id is None


async def test_only_super_admins_can_connect(client, configured) -> None:
    from neocloud.main import app

    mb = await _mailbox(client)
    roles = ["SALES_MANAGER"]
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        subject="m", email=None, roles=roles, permissions=permissions_for_roles(roles))
    try:
        assert (await client.post(f"{V1}/email-sync/mailboxes/{mb['id']}/connect")).status_code == 403
        assert (await client.post(f"{V1}/email-sync/oauth/callback", json={"code": "x", "state": "y"})).status_code == 403
        assert (await client.post(f"{V1}/email-sync/mailboxes/{mb['id']}/disconnect")).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# --------------------------------------------------------------------------- #
# Syncing connected mailboxes
# --------------------------------------------------------------------------- #
async def test_make_reader_only_for_connected_healthy_mailboxes(configured) -> None:
    mb = Mailbox(address="crm@tensorbay.io")
    assert make_reader(configured, mb) is None  # not connected
    mb.refresh_token_enc = oauth.encrypt_token(configured, "rt")
    assert isinstance(make_reader(configured, mb), GmailReader)
    mb.needs_reconnect = True
    assert make_reader(configured, mb) is None
    mb.needs_reconnect = False
    assert make_reader(_settings(gmail_oauth_json="{}"), mb) is None  # client not configured


async def test_run_sync_once_skips_unconnected_and_syncs_connected(client, session, configured, monkeypatch) -> None:
    cid = (await client.post(f"{V1}/customers", json={"legal_name": "Akash", "status": "PROSPECT"})).json()["id"]
    await client.post(f"{V1}/customers/{cid}/contacts", json={"type": "COMMERCIAL", "name": "Joe", "email": "joe@akash.network"})
    connected = Mailbox(address="crm@tensorbay.io", capture_unmatched=True, refresh_token_enc=oauth.encrypt_token(configured, "rt"))
    idle = Mailbox(address="lizi@tensorbay.io")
    session.add_all([connected, idle])
    await session.commit()

    readers = {"crm@tensorbay.io": FakeReader({"a": gmail_msg("a", "joe@akash.network", "crm@tensorbay.io", "Hello")})}
    monkeypatch.setattr(service, "make_reader", lambda s, mb: readers.get(mb.address) if mb.refresh_token_enc else None)
    out = await service.run_sync_once(session, configured)
    assert list(out) == ["crm@tensorbay.io"] and out["crm@tensorbay.io"].logged == 1
    assert len((await client.get(f"{V1}/customers/{cid}/activities")).json()) == 1


async def test_revoked_grant_flags_the_mailbox_for_reconnect(client, session, configured, monkeypatch) -> None:
    mb = Mailbox(address="crm@tensorbay.io", refresh_token_enc=oauth.encrypt_token(configured, "rt"))
    session.add(mb)
    await session.commit()

    class Revoked(FakeReader):
        async def current_history_id(self):
            raise Exception("('invalid_grant: Token has been expired or revoked.', {...})")

    await service.sync_mailbox(session, Revoked({}), mb, configured)
    await session.commit()
    assert mb.needs_reconnect is True and "Reconnect" in mb.last_error
    # Not retried every cycle, and "Sync now" explains what to do.
    assert make_reader(configured, mb) is None
    r = await client.post(f"{V1}/email-sync/mailboxes/{mb.id}/sync")
    assert r.status_code == 409 and "Reconnect" in r.json()["detail"]
