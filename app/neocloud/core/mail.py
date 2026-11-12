"""Shared helpers for platform-sent email (SES)."""

from email.utils import formataddr

from neocloud.core.config import Settings


def ses_source(settings: Settings) -> str | None:
    """The ``From`` value for every email the platform sends.

    ``TensorBay <crm@tensorbay.io>`` when a display name is configured, otherwise
    the bare address. ``None`` when no sender is configured (callers then skip
    sending / fall back). The address must be a verified SES identity.
    """
    addr = (settings.ses_from_email or "").strip()
    if not addr:
        return None
    name = (settings.ses_from_name or "").strip()
    # formataddr RFC 2047-encodes non-ASCII names and quotes specials, and the
    # name is operator config - strip CR/LF so it can never inject headers.
    name = name.replace("\r", " ").replace("\n", " ")
    return formataddr((name, addr)) if name else addr
