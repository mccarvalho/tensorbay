"""Google OAuth for mailbox connections (no service-account key, no delegation).

A Super Admin clicks "Connect Gmail" for a mailbox; the mailbox owner signs in to
Google and approves read-only Gmail access. We keep only the resulting refresh
token, Fernet-encrypted in the database. The encryption key and the OAuth client
live in Secrets Manager.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import boto3
import httpx
from cryptography.fernet import Fernet, InvalidToken

from neocloud.core.config import Settings
from neocloud.core.logging import get_logger

logger = get_logger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
LOGIN_SCOPES = ["openid", "email", GMAIL_SCOPE]
STATE_TTL_SECONDS = 600
_SECRET_TTL = 300
_secret_cache: dict[str, tuple[float, dict | None]] = {}


class OAuthError(Exception):
    """A user-presentable problem completing the connection."""


@dataclass
class OAuthClient:
    client_id: str
    client_secret: str


@dataclass
class ExchangeResult:
    refresh_token: str
    email: str


# --------------------------------------------------------------------------- #
# Secrets
# --------------------------------------------------------------------------- #
def _secret_json(settings: Settings, arn: str | None, override: str | None) -> dict | None:
    raw = override
    if not raw and arn:
        cached = _secret_cache.get(arn)
        now = time.monotonic()
        if cached and now - cached[0] < _SECRET_TTL:
            return cached[1]
        try:
            client = boto3.client("secretsmanager", region_name=settings.aws_region)
            raw = client.get_secret_value(SecretId=arn)["SecretString"]
        except Exception as exc:  # noqa: BLE001
            logger.error("gmail_secret_fetch_failed", error=str(exc))
            return None
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        parsed = None
    data = parsed if isinstance(parsed, dict) else None
    if arn and not override:
        _secret_cache[arn] = (time.monotonic(), data)
    return data


def load_oauth_client(settings: Settings) -> OAuthClient | None:
    data = _secret_json(settings, settings.gmail_oauth_secret_arn, settings.gmail_oauth_json)
    if data and data.get("client_id") and data.get("client_secret"):
        return OAuthClient(str(data["client_id"]).strip(), str(data["client_secret"]).strip())
    return None


def _fernet(settings: Settings) -> Fernet | None:
    key = settings.gmail_token_key
    if not key:
        data = _secret_json(settings, settings.gmail_token_key_secret_arn, None)
        key = (data or {}).get("key")
    if not key:
        return None
    key = str(key).strip()
    key += "=" * (-len(key) % 4)  # Terraform's url-safe base64 omits padding
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError):
        logger.error("gmail_token_key_invalid")
        return None


def is_configured(settings: Settings) -> bool:
    return load_oauth_client(settings) is not None and _fernet(settings) is not None


def redirect_uri(settings: Settings) -> str:
    return f"{settings.app_base_url.rstrip('/')}/email/oauth/callback"


# --------------------------------------------------------------------------- #
# Token encryption + signed state
# --------------------------------------------------------------------------- #
def encrypt_token(settings: Settings, token: str) -> str:
    f = _fernet(settings)
    if f is None:
        raise OAuthError("Token encryption key is not configured")
    return f.encrypt(token.encode()).decode()


def decrypt_token(settings: Settings, blob: str) -> str | None:
    f = _fernet(settings)
    if f is None:
        return None
    try:
        return f.decrypt(blob.encode()).decode()
    except InvalidToken:
        logger.error("gmail_token_decrypt_failed")
        return None


def make_state(settings: Settings, mailbox_id: str, user_sub: str) -> str:
    f = _fernet(settings)
    if f is None:
        raise OAuthError("Token encryption key is not configured")
    payload = json.dumps({"m": mailbox_id, "u": user_sub}).encode()
    return base64.urlsafe_b64encode(f.encrypt(payload)).decode()


def parse_state(settings: Settings, state: str, user_sub: str) -> str:
    """Return the mailbox id the state was issued for, or raise OAuthError.

    The state is encrypted + timestamped by Fernet (so it can't be forged or
    replayed after ``STATE_TTL_SECONDS``) and bound to the admin who started it.
    """
    f = _fernet(settings)
    if f is None:
        raise OAuthError("Token encryption key is not configured")
    try:
        raw = f.decrypt(base64.urlsafe_b64decode(state.encode()), ttl=STATE_TTL_SECONDS)
        data = json.loads(raw)
    except (InvalidToken, ValueError):
        raise OAuthError("This connection attempt expired. Start again from the Email page.") from None
    if data.get("u") != user_sub:
        raise OAuthError("This connection was started by a different user.")
    return str(data["m"])


# --------------------------------------------------------------------------- #
# Google round trips
# --------------------------------------------------------------------------- #
def authorization_url(settings: Settings, mailbox_address: str, state: str) -> str:
    client = load_oauth_client(settings)
    if client is None:
        raise OAuthError("Google OAuth client is not configured")
    params = {
        "client_id": client.client_id,
        "redirect_uri": redirect_uri(settings),
        "response_type": "code",
        "scope": " ".join(LOGIN_SCOPES),
        "access_type": "offline",  # gives us a refresh token
        "prompt": "consent",  # ...every time, even if approved before
        "login_hint": mailbox_address,
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(settings: Settings, code: str) -> ExchangeResult:
    client = load_oauth_client(settings)
    if client is None:
        raise OAuthError("Google OAuth client is not configured")
    async with httpx.AsyncClient(timeout=20) as http:
        resp = await http.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": client.client_id,
                "client_secret": client.client_secret,
                "redirect_uri": redirect_uri(settings),
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code != 200:
            logger.warning("gmail_code_exchange_failed", status=resp.status_code, body=resp.text[:300])
            raise OAuthError("Google rejected the authorization code. Please try connecting again.")
        tok = resp.json()
        refresh = tok.get("refresh_token")
        if not refresh:
            raise OAuthError("Google did not return a refresh token. Please try connecting again.")
        if GMAIL_SCOPE not in (tok.get("scope") or "").split():
            raise OAuthError("Read access to Gmail was not granted. Approve every permission requested.")
        info = await http.get(USERINFO_URL, headers={"Authorization": f"Bearer {tok['access_token']}"})
        if info.status_code != 200 or not info.json().get("email"):
            raise OAuthError("Could not confirm which Google account was used.")
        data = info.json()
        if data.get("email_verified") is False:
            raise OAuthError("That Google account's email is not verified.")
    return ExchangeResult(refresh_token=refresh, email=str(data["email"]).strip().lower())


async def revoke_token(token: str) -> None:
    """Best effort: tell Google to drop the grant. Never raises."""
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            await http.post(REVOKE_URL, data={"token": token})
    except Exception as exc:  # noqa: BLE001
        logger.warning("gmail_revoke_failed", error=str(exc))
