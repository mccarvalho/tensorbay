"""Normalisation helpers for inbound website lead submissions.

The website form is not under our control, so we are deliberately tolerant:
empty markers ("", "-", "—", "n/a" ...) become ``None``, numbers may arrive as
strings, and the region may either be sent as structured fields or still be
embedded in the free-text message ("Region for your quote: North America ·
United States") as it is in the original notification email.
"""

from __future__ import annotations

import re

# Values the form/email template uses to mean "not provided".
_EMPTY_MARKERS = {"", "-", "--", "—", "–", "n/a", "na", "none", "null", "undefined"}

_REGION_LINE = re.compile(r"^\s*Region for your quote:\s*(?P<value>.+?)\s*$", re.I | re.M)
_REGION_SPLIT = re.compile(r"\s*[·|•]\s*")


def clean(value: object) -> str | None:
    """Return a stripped string, or ``None`` if the value is empty/a marker."""
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _EMPTY_MARKERS:
        return None
    return text


def parse_gpu_count(value: object) -> int | None:
    """Best-effort positive integer from "8", "8 GPUs", "1,024", 8, 8.0."""
    text = clean(value)
    if text is None:
        return None
    match = re.search(r"\d[\d,]*", text)
    if not match:
        return None
    try:
        number = int(match.group(0).replace(",", ""))
    except ValueError:
        return None
    return number if number > 0 else None


def split_region(value: str | None) -> tuple[str | None, str | None]:
    """Split "North America · United States" into (region, country)."""
    text = clean(value)
    if text is None:
        return None, None
    parts = [p for p in _REGION_SPLIT.split(text) if p.strip()]
    if not parts:
        return None, None
    region = parts[0].strip()
    country = parts[1].strip() if len(parts) > 1 else None
    return region, country


def extract_region_from_message(
    message: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Pull an embedded "Region for your quote:" line out of the message.

    Returns ``(region, country, message_without_region_line)``. If there is no
    such line the message is returned unchanged.
    """
    if not message:
        return None, None, message
    match = _REGION_LINE.search(message)
    if not match:
        return None, None, message
    region, country = split_region(match.group("value"))
    remaining = (message[: match.start()] + message[match.end() :]).strip()
    return region, country, (remaining or None)


def region_matches(configured: str | None, region: str | None, country: str | None) -> bool:
    """Does a rep's comma-separated ``configured`` regions cover this lead?

    Tokens are compared case-insensitively against the lead's region and
    country. Anything shorter than 4 characters ("us", "eu") must match
    exactly so it can't match inside unrelated words ("australia"); longer
    values may match as substrings.
    """
    if not configured:
        return False
    targets = [t.lower() for t in (region, country) if t]
    if not targets:
        return False
    for token in re.split(r"[,;]", configured):
        tok = token.strip().lower()
        if not tok:
            continue
        for target in targets:
            if tok == target:
                return True
            if len(tok) >= 4 and len(target) >= 4 and (tok in target or target in tok):
                return True
    return False
