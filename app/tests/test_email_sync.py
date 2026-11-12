"""Gmail sync: parsing, matching, dedupe, unmatched triage and the cursor."""

import base64

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from neocloud.core.config import get_settings
from neocloud.domains.customers.models import Activity
from neocloud.domains.emailsync.gmail import HistoryExpired
from neocloud.domains.emailsync.models import Mailbox, UnmatchedEmail
from neocloud.domains.emailsync.parsing import (
    clean_body,
    forwarded_addresses,
    html_to_text,
    parse_addresses,
    parse_gmail_message,
)
from neocloud.domains.emailsync.service import sync_mailbox

V1 = "/v1"


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def gmail_msg(
    mid: str, frm: str, to: str, subject: str = "Hello", body: str = "Hi there",
    cc: str | None = None, date: str = "Mon, 09 Nov 2026 15:00:00 -0500", html: str | None = None,
) -> dict:
    headers = [
        {"name": "Message-ID", "value": f"<{mid}@mail.gmail.com>"},
        {"name": "From", "value": frm}, {"name": "To", "value": to},
        {"name": "Subject", "value": subject}, {"name": "Date", "value": date},
    ]
    if cc:
        headers.append({"name": "Cc", "value": cc})
    parts = [{"mimeType": "text/plain", "body": {"data": _b64(body)}}]
    if html:
        parts.append({"mimeType": "text/html", "body": {"data": _b64(html)}})
    return {"id": mid, "payload": {"mimeType": "multipart/alternative", "headers": headers, "parts": parts}}


class FakeReader:
    def __init__(self, messages: dict[str, dict], history: list[str] | None = None, cursor: str = "100"):
        self.messages, self.history, self.cursor = messages, history, cursor
        self.expired = False
        self.calls: list[str] = []

    async def current_history_id(self) -> str:
        return self.cursor

    async def list_recent(self, lookback_days: int, limit: int) -> list[str]:
        self.calls.append("list_recent")
        return list(self.messages)

    async def history_added(self, start: str):
        self.calls.append("history")
        if self.expired:
            raise HistoryExpired()
        return (self.history or [], self.cursor)

    async def get_message(self, message_id: str):
        return self.messages.get(message_id)


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def test_parse_addresses_lowercases_and_dedupes() -> None:
    got = parse_addresses('"Deng, Joe" <Joe@Akash.Network>, joe@akash.network', "Bob <b@x.com>")
    assert got == ["joe@akash.network", "b@x.com"]


def test_clean_body_strips_quoted_history() -> None:
    body = "Sounds good, let's do Tuesday.\n\nOn Mon, Nov 9, 2026 at 3:00 PM Bob <b@x.com> wrote:\n> earlier text\n> more"
    assert clean_body(body) == "Sounds good, let's do Tuesday."
    # A sentence that merely starts with "On" is kept.
    assert clean_body("On Monday we ship.\nThanks") == "On Monday we ship.\nThanks"
    outlook = "Yes.\n\nFrom: Bob <b@x.com>\nSent: Monday\nTo: me\nSubject: Re: x\nold stuff"
    assert clean_body(outlook) == "Yes."
    assert clean_body("From: now on we use H200.\nOk") == "From: now on we use H200.\nOk"
    assert len(clean_body("x" * 20000)) < 8100


def test_html_only_bodies_become_text() -> None:
    assert "Hello Joe" in html_to_text("<html><style>p{}</style><body><p>Hello <b>Joe</b></p></body></html>")


def test_forwarded_addresses_found_in_header_block() -> None:
    txt = "FYI\n---------- Forwarded message ---------\nFrom: Joe <Joe@Akash.network>\nTo: Bruno <bramos@tensorbay.io>\nCc: x@y.com\n"
    assert forwarded_addresses(txt) == ["joe@akash.network", "bramos@tensorbay.io", "x@y.com"]
    assert forwarded_addresses("no forward here from a@b.com") == []


def test_parse_gmail_message_fields_and_forward_keeps_body() -> None:
    p = parse_gmail_message(gmail_msg("m1", "Joe <joe@akash.network>", "bramos@tensorbay.io", cc="c@z.com"))
    assert p and p.from_addr == "joe@akash.network" and p.cc_addrs == ["c@z.com"]
    assert p.sent_at.isoformat() == "2026-11-09T20:00:00+00:00"
    assert p.message_id == "<m1@mail.gmail.com>"
    fwd = parse_gmail_message(gmail_msg(
        "m2", "bruno@tensorbay.io", "crm@tensorbay.io", subject="Fwd: pricing",
        body="FYI\n---------- Forwarded message ---------\nFrom: joe@akash.network\n> quoted but kept\nreal content",
    ))
    assert fwd and "real content" in fwd.body_text and "quoted but kept" in fwd.body_text
    assert "joe@akash.network" in fwd.forwarded_addrs
    assert parse_gmail_message({"id": "x", "payload": {"headers": []}}) is None


# --------------------------------------------------------------------------- #
# Matching + sync
# --------------------------------------------------------------------------- #
async def _customer_with_contact(client: AsyncClient, name: str, email: str) -> tuple[str, str]:
    cid = (await client.post(f"{V1}/customers", json={"legal_name": name, "status": "PROSPECT"})).json()["id"]
    ct = (await client.post(f"{V1}/customers/{cid}/contacts", json={"type": "COMMERCIAL", "name": "Joe", "email": email})).json()
    return cid, ct["id"]


async def _mailbox(session, capture: bool = True, history: str | None = None) -> Mailbox:
    mb = Mailbox(address="crm@tensorbay.io", capture_unmatched=capture, history_id=history)
    session.add(mb)
    await session.flush()
    return mb


async def test_matching_email_becomes_an_activity_with_direction(client, session) -> None:
    cid, contact_id = await _customer_with_contact(client, "Akash", "joe@akash.network")
    mb = await _mailbox(session)
    reader = FakeReader({
        "in1": gmail_msg("in1", "Joe <JOE@akash.network>", "bruno@tensorbay.io", "GB200 quote", "Can you quote 216 GPUs?"),
        "out1": gmail_msg("out1", "bruno@tensorbay.io", "joe@akash.network", "Re: GB200 quote", "Sent the quote."),
        "internal": gmail_msg("internal", "bruno@tensorbay.io", "lizi@tensorbay.io", "lunch", "noon?"),
    })
    res = await sync_mailbox(session, reader, mb, get_settings())
    await session.commit()
    assert (res.logged, res.unmatched) == (2, 0) and res.skipped == 1  # internal-only is ignored

    acts = (await client.get(f"{V1}/customers/{cid}/activities")).json()
    by_subject = {a["subject"]: a for a in acts}
    assert by_subject["GB200 quote"]["direction"] == "IN" and by_subject["GB200 quote"]["source"] == "gmail"
    assert by_subject["Re: GB200 quote"]["direction"] == "OUT"
    assert all(a["type"] == "EMAIL" and a["contact_id"] == contact_id for a in acts)
    assert by_subject["GB200 quote"]["occurred_at"].startswith("2026-11-09T20:00")
    assert mb.history_id == "100" and mb.last_logged == 2 and mb.last_error is None


async def test_resync_is_idempotent_and_uses_history_cursor(client, session) -> None:
    cid, _ = await _customer_with_contact(client, "Akash", "joe@akash.network")
    mb = await _mailbox(session)
    msg = gmail_msg("a1", "joe@akash.network", "crm@tensorbay.io", "Hi")
    r1 = FakeReader({"a1": msg})
    await sync_mailbox(session, r1, mb, get_settings())
    assert r1.calls == ["list_recent"]  # first run: lookback
    # Second run replays the same message via history (e.g. cursor overlap): no duplicate.
    r2 = FakeReader({"a1": msg}, history=["a1"], cursor="101")
    res = await sync_mailbox(session, r2, mb, get_settings())
    await session.commit()
    assert r2.calls == ["history"] and res.logged == 0 and mb.history_id == "101"
    assert len((await client.get(f"{V1}/customers/{cid}/activities")).json()) == 1
    # Expired cursor falls back to a fresh lookback instead of failing.
    r3 = FakeReader({"a1": msg}); r3.expired = True
    await sync_mailbox(session, r3, mb, get_settings())
    assert r3.calls == ["history", "list_recent"] and mb.last_error is None


async def test_same_email_logged_on_each_matching_customer_once(client, session) -> None:
    c1, _ = await _customer_with_contact(client, "Akash", "joe@akash.network")
    c2, _ = await _customer_with_contact(client, "Foxgaroo", "kevin@foxgaroo.ai")
    mb = await _mailbox(session)
    reader = FakeReader({"t": gmail_msg("t", "bruno@tensorbay.io", "joe@akash.network, kevin@foxgaroo.ai", "Intro")})
    res = await sync_mailbox(session, reader, mb, get_settings())
    await session.commit()
    assert res.logged == 2
    for cid in (c1, c2):
        assert len((await client.get(f"{V1}/customers/{cid}/activities")).json()) == 1


async def test_cc_and_forwarded_headers_are_matched(client, session) -> None:
    cid, _ = await _customer_with_contact(client, "Akash", "joe@akash.network")
    mb = await _mailbox(session)
    reader = FakeReader({
        "cc": gmail_msg("cc", "bruno@tensorbay.io", "lizi@tensorbay.io", "FYI", cc="Joe <joe@akash.network>"),
        "fw": gmail_msg("fw", "lizi@tensorbay.io", "crm@tensorbay.io", "Fwd: terms",
                        body="see below\n---------- Forwarded message ---------\nFrom: joe@akash.network\nTo: lizi@tensorbay.io\n\nterms attached"),
    })
    res = await sync_mailbox(session, reader, mb, get_settings())
    await session.commit()
    assert res.logged == 2
    assert len((await client.get(f"{V1}/customers/{cid}/activities")).json()) == 2


async def test_unmatched_crm_email_is_queued_but_seller_mailbox_drops_it(client, session) -> None:
    msg = gmail_msg("u1", "new@stranger.io", "crm@tensorbay.io", "Pricing?", "How much for 8 H100?")
    crm = await _mailbox(session, capture=True)
    res = await sync_mailbox(session, FakeReader({"u1": msg}), crm, get_settings())
    await session.commit()
    assert res.unmatched == 1
    rows = (await session.execute(select(UnmatchedEmail))).scalars().all()
    assert rows[0].external_addrs == "new@stranger.io" and rows[0].direction == "IN"
    # Re-sync does not queue it twice.
    await sync_mailbox(session, FakeReader({"u1": msg}), crm, get_settings())
    await session.commit()
    assert len((await session.execute(select(UnmatchedEmail))).scalars().all()) == 1

    seller = Mailbox(address="lizi@tensorbay.io", capture_unmatched=False)
    session.add(seller)
    await session.flush()
    res2 = await sync_mailbox(session, FakeReader({"p": gmail_msg("p", "friend@gmail.com", "lizi@tensorbay.io", "dinner")}), seller, get_settings())
    assert res2.unmatched == 0 and res2.skipped == 1
    assert len((await session.execute(select(UnmatchedEmail))).scalars().all()) == 1  # nothing private stored


async def test_one_bad_message_does_not_stop_the_run(client, session) -> None:
    cid, _ = await _customer_with_contact(client, "Akash", "joe@akash.network")
    mb = await _mailbox(session)
    reader = FakeReader({
        "bad": {"id": "bad", "payload": {"headers": [{"name": "From", "value": "x"}]}},
        "ok": gmail_msg("ok", "joe@akash.network", "crm@tensorbay.io", "Works"),
    })
    res = await sync_mailbox(session, reader, mb, get_settings())
    await session.commit()
    assert res.logged == 1 and mb.last_error is None


async def test_reader_failure_is_recorded_not_raised(session) -> None:
    mb = await _mailbox(session)

    class Boom(FakeReader):
        async def current_history_id(self):
            raise RuntimeError("delegation denied")

    await sync_mailbox(session, Boom({}), mb, get_settings())
    assert "delegation denied" in (mb.last_error or "") and mb.last_sync_at is not None


# --------------------------------------------------------------------------- #
# API: triage queue + mailbox admin
# --------------------------------------------------------------------------- #
async def test_assign_unmatched_logs_activity_and_creates_contact(client, session) -> None:
    cid = (await client.post(f"{V1}/customers", json={"legal_name": "Stranger Inc", "status": "PROSPECT"})).json()["id"]
    crm = await _mailbox(session)
    await sync_mailbox(session, FakeReader({"u1": gmail_msg("u1", "new@stranger.io", "crm@tensorbay.io", "Pricing?", "How much?")}), crm, get_settings())
    await session.commit()

    queue = (await client.get(f"{V1}/email-sync/unmatched")).json()
    assert len(queue) == 1
    r = await client.post(f"{V1}/email-sync/unmatched/{queue[0]['id']}/assign",
                          json={"customer_id": cid, "contact_name": "New Person", "contact_role": "CTO"})
    assert r.status_code == 200 and r.json()["status"] == "ASSIGNED"
    contacts = (await client.get(f"{V1}/customers/{cid}/contacts")).json()
    assert contacts[0]["email"] == "new@stranger.io" and contacts[0]["role"] == "CTO"
    acts = (await client.get(f"{V1}/customers/{cid}/activities")).json()
    assert acts[0]["subject"] == "Pricing?" and acts[0]["source"] == "gmail"
    assert (await client.get(f"{V1}/email-sync/unmatched")).json() == []
    # Can't assign twice.
    assert (await client.post(f"{V1}/email-sync/unmatched/{queue[0]['id']}/assign", json={"customer_id": cid})).status_code == 409
    # Future mail from that address now matches automatically.
    crm2 = (await session.execute(select(Mailbox))).scalars().first()
    res = await sync_mailbox(session, FakeReader({"u2": gmail_msg("u2", "new@stranger.io", "crm@tensorbay.io", "Follow up")}, history=["u2"], cursor="102"), crm2, get_settings())
    assert res.logged == 1


async def test_dismiss_drops_the_body(client, session) -> None:
    crm = await _mailbox(session)
    await sync_mailbox(session, FakeReader({"u1": gmail_msg("u1", "spam@x.io", "crm@tensorbay.io", "Buy now", "secret body")}), crm, get_settings())
    await session.commit()
    item = (await client.get(f"{V1}/email-sync/unmatched")).json()[0]
    r = await client.post(f"{V1}/email-sync/unmatched/{item['id']}/dismiss")
    assert r.status_code == 200 and r.json()["body_text"] is None and r.json()["status"] == "DISMISSED"


async def test_mailbox_admin_and_status(client) -> None:
    st = (await client.get(f"{V1}/email-sync/status")).json()
    assert st["configured"] is False and st["mailboxes"] == [] and st["pending_unmatched"] == 0
    made = await client.post(f"{V1}/email-sync/mailboxes", json={"address": "CRM@tensorbay.io", "capture_unmatched": True})
    assert made.status_code == 201 and made.json()["address"] == "crm@tensorbay.io"
    assert (await client.post(f"{V1}/email-sync/mailboxes", json={"address": "crm@tensorbay.io"})).status_code == 409
    mid = made.json()["id"]
    assert (await client.patch(f"{V1}/email-sync/mailboxes/{mid}", json={"enabled": False})).json()["enabled"] is False
    # Sync without a service account is a clear 409, not a crash.
    assert (await client.post(f"{V1}/email-sync/mailboxes/{mid}/sync")).status_code == 409
    assert (await client.delete(f"{V1}/email-sync/mailboxes/{mid}")).status_code == 204


async def test_non_admins_cannot_manage_mailboxes(client) -> None:
    from neocloud.auth.dependencies import CurrentUser, get_current_user
    from neocloud.auth.rbac import permissions_for_roles
    from neocloud.main import app

    roles = ["SALES_MANAGER"]
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        subject="m", email=None, roles=roles, permissions=permissions_for_roles(roles))
    try:
        assert (await client.post(f"{V1}/email-sync/mailboxes", json={"address": "a@tensorbay.io"})).status_code == 403
        assert (await client.get(f"{V1}/email-sync/unmatched")).status_code == 200  # sales can triage
    finally:
        app.dependency_overrides.pop(get_current_user, None)
