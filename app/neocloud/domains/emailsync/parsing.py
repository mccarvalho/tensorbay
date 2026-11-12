"""Pure helpers: turn a Gmail API message into a clean, storable email."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser

MAX_BODY_CHARS = 8000
MAX_SUBJECT_CHARS = 500


@dataclass
class ParsedEmail:
    message_id: str
    subject: str
    from_addr: str
    to_addrs: list[str]
    cc_addrs: list[str]
    sent_at: datetime
    body_text: str
    forwarded_addrs: list[str] = field(default_factory=list)

    @property
    def participants(self) -> list[str]:
        seen: dict[str, None] = {}
        for a in [self.from_addr, *self.to_addrs, *self.cc_addrs, *self.forwarded_addrs]:
            if a:
                seen.setdefault(a, None)
        return list(seen)


# --------------------------------------------------------------------------- #
# Addresses
# --------------------------------------------------------------------------- #
_ADDR_RE = re.compile(r"[A-Za-z0-9._%+\-']+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def parse_addresses(*header_values: str | None) -> list[str]:
    out: dict[str, None] = {}
    for _, addr in getaddresses([v for v in header_values if v]):
        addr = addr.strip().lower()
        if addr and "@" in addr:
            out.setdefault(addr, None)
    return list(out)


def domain_of(addr: str) -> str:
    return addr.rsplit("@", 1)[-1].lower()


def is_internal(addr: str, internal_domains: set[str]) -> bool:
    return domain_of(addr) in internal_domains


# --------------------------------------------------------------------------- #
# Body
# --------------------------------------------------------------------------- #
class _TextExtractor(HTMLParser):
    _BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        if tag in ("script", "style", "head"):
            self._skip += 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag in ("script", "style", "head"):
            self._skip = max(0, self._skip - 1)
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):  # noqa: ANN001
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    p = _TextExtractor()
    p.feed(html)
    return "".join(p.parts)


# Where the quoted history of a reply starts. Everything after is dropped so the
# timeline shows what was actually said in this message.
_QUOTE_STARTS = [
    re.compile(r"^\s*On .{5,200}wrote:\s*$", re.I),
    re.compile(r"^\s*On .{5,120}$", re.I),  # "On Mon, ..." wrapped onto the next line
    re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}", re.I),
    re.compile(r"^\s*-{2,}\s*Forwarded message\s*-{2,}", re.I),
    re.compile(r"^\s*_{5,}\s*$"),
    re.compile(r"^\s*(From|De):\s.+", re.I),  # Outlook-style header block
    re.compile(r"^\s*Em .{5,200}escreveu:\s*$", re.I),
    re.compile(r"^\s*El .{5,200}escribi", re.I),
]


_FWD_SUBJECT = re.compile(r"^\s*(fwd?|enc|rv|tr)\s*:", re.I)


def is_forward(subject: str) -> bool:
    return bool(_FWD_SUBJECT.match(subject))


def clean_body(text: str, limit: int = MAX_BODY_CHARS, keep_quoted: bool = False) -> str:
    """Drop quoted reply history. A forward keeps everything: the forwarded
    message is the whole point of it."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    kept: list[str] = []
    for i, line in enumerate(lines):
        if keep_quoted:
            kept.append(line.lstrip("> ").rstrip() if line.lstrip().startswith(">") else line)
            continue
        if line.lstrip().startswith(">"):
            continue
        if _QUOTE_STARTS[0].match(line):
            break
        # A bare "On ..." line only counts as a quote marker when the next line
        # finishes it ("... wrote:").
        if _QUOTE_STARTS[1].match(line):
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if re.search(r"wrote:\s*$", nxt, re.I):
                break
            kept.append(line)
            continue
        if any(rx.match(line) for j, rx in enumerate(_QUOTE_STARTS) if j != 1):
            # Only treat a "From:" line as a quote header if a Sent/Date/To line
            # follows - otherwise a normal sentence like "From: now on..." stays.
            if _QUOTE_STARTS[5].match(line):
                tail = "\n".join(lines[i + 1 : i + 4])
                if not re.search(r"^\s*(Sent|Date|Enviado|To|Para):", tail, re.I | re.M):
                    kept.append(line)
                    continue
            break
        kept.append(line)
    out = "\n".join(kept)
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    if len(out) > limit:
        out = out[:limit].rstrip() + "\n[…truncated]"
    return out


_FWD_HEADER = re.compile(r"^\s*(From|To|Cc|De|Para)\s*:\s*(.+)$", re.I | re.M)


def forwarded_addresses(text: str) -> list[str]:
    """Addresses in a forwarded-message header block (first ~3000 chars).

    A seller forwarding a customer email to crm@ shows up as seller -> crm@, so the
    real customer only appears inside the forwarded headers."""
    head = text.replace("\r\n", "\n")
    marker = re.search(r"(Forwarded message|Original Message|Mensagem encaminhada)", head, re.I)
    if not marker:
        return []
    block = head[marker.end() : marker.end() + 3000]
    found: dict[str, None] = {}
    for m in _FWD_HEADER.finditer(block):
        for a in _ADDR_RE.findall(m.group(2)):
            found.setdefault(a.lower(), None)
    return list(found)


# --------------------------------------------------------------------------- #
# Gmail message -> ParsedEmail
# --------------------------------------------------------------------------- #
def _b64(data: str) -> str:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad).decode("utf-8", errors="replace")


def _walk(part: dict):
    yield part
    for sub in part.get("parts") or []:
        yield from _walk(sub)


def extract_body(payload: dict) -> str:
    plain: list[str] = []
    html: list[str] = []
    for part in _walk(payload):
        mime = (part.get("mimeType") or "").lower()
        data = (part.get("body") or {}).get("data")
        if not data or part.get("filename"):
            continue
        if mime == "text/plain":
            plain.append(_b64(data))
        elif mime == "text/html":
            html.append(_b64(data))
    if plain:
        return "\n".join(plain)
    if html:
        return html_to_text("\n".join(html))
    return ""


def _header(headers: list[dict], name: str) -> str | None:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value")
    return None


def parse_gmail_message(msg: dict) -> ParsedEmail | None:
    payload = msg.get("payload") or {}
    headers = payload.get("headers") or []
    message_id = (_header(headers, "Message-ID") or _header(headers, "Message-Id") or "").strip()
    if not message_id:
        message_id = f"gmail:{msg.get('id')}"
    from_list = parse_addresses(_header(headers, "From"))
    if not from_list:
        return None

    sent_at: datetime | None = None
    raw_date = _header(headers, "Date")
    if raw_date:
        try:
            sent_at = parsedate_to_datetime(raw_date)
        except (TypeError, ValueError):
            sent_at = None
    if sent_at is None and msg.get("internalDate"):
        sent_at = datetime.fromtimestamp(int(msg["internalDate"]) / 1000, tz=timezone.utc)
    if sent_at is None:
        sent_at = datetime.now(timezone.utc)
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)

    raw_body = extract_body(payload)
    subject = " ".join((_header(headers, "Subject") or "(no subject)").split())
    fwd = is_forward(subject)
    return ParsedEmail(
        message_id=message_id[:255],
        subject=subject[:MAX_SUBJECT_CHARS],
        from_addr=from_list[0],
        to_addrs=parse_addresses(_header(headers, "To"), _header(headers, "Delivered-To")),
        cc_addrs=parse_addresses(_header(headers, "Cc")),
        sent_at=sent_at.astimezone(timezone.utc),
        body_text=clean_body(raw_body, keep_quoted=fwd),
        forwarded_addrs=forwarded_addresses(raw_body),
    )
