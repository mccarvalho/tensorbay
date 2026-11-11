"""Cognito Pre sign-up trigger: link a Google sign-in to the invited user.

Why: administrators "invite" a person, which creates a *native* Cognito user and
puts their roles (Cognito groups) on it. When that person then signs in with
Google, Cognito by default creates a SECOND, role-less user (``Google_<id>``),
so they hit 403s and the user list shows a duplicate.

This trigger runs when a federated user signs in for the first time. If an
invited native user with the same email exists, it links the Google identity to
that user, so the sign-in resolves to the invited user and its groups.

Safety rules (this links accounts by email, so it must be conservative):
  * only the ``Google`` provider, only when Google asserts ``email_verified``;
  * only link to a NATIVE user (never another federated one);
  * exactly one match, matched on the exact (lower-cased) email;
  * on anything unexpected, do nothing and log - never block the sign-in.
"""

import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_client = None


def _cognito():
    global _client
    if _client is None:
        _client = boto3.client("cognito-idp")
    return _client


def _is_true(value) -> bool:
    return str(value).strip().lower() == "true"


def _native_users_for(pool_id: str, email: str) -> list[dict]:
    """Native (non-federated) users whose email matches exactly."""
    found: list[dict] = []
    token = None
    while True:
        kwargs = {"UserPoolId": pool_id, "Filter": f'email = "{email}"', "Limit": 10}
        if token:
            kwargs["PaginationToken"] = token
        resp = _cognito().list_users(**kwargs)
        for user in resp.get("Users", []):
            if user.get("UserStatus") == "EXTERNAL_PROVIDER":
                continue
            attrs = {a["Name"]: a["Value"] for a in user.get("Attributes", [])}
            # Defence in depth: the filter is exact, but re-check the value.
            if attrs.get("email", "").lower() == email:
                found.append(user)
        token = resp.get("PaginationToken")
        if not token:
            return found


def handler(event, context):
    try:
        if event.get("triggerSource") != "PreSignUp_ExternalProvider":
            return event

        pool_id = event["userPoolId"]
        attrs = event["request"].get("userAttributes", {})
        email = (attrs.get("email") or "").strip().lower()
        provider, _, subject = (event.get("userName") or "").partition("_")

        if provider != "Google" or not subject:
            logger.info("skip: not a Google sign-in (%s)", provider)
            return event
        if not email:
            logger.info("skip: no email on the federated identity")
            return event
        if '"' in email or "\\" in email:
            # The email is used inside a Cognito filter expression; never
            # interpolate characters that could alter it.
            logger.warning("skip: email contains characters not allowed in a filter")
            return event
        if not _is_true(attrs.get("email_verified")):
            # Never link on an email the IdP hasn't verified (takeover risk).
            logger.warning("skip: email not verified by the identity provider")
            return event

        matches = _native_users_for(pool_id, email)
        if not matches:
            logger.info("no invited user for this email; leaving as-is")
            return event
        if len(matches) > 1:
            logger.error("ambiguous: %d native users share this email; not linking", len(matches))
            return event

        native = matches[0]
        _cognito().admin_link_provider_for_user(
            UserPoolId=pool_id,
            DestinationUser={
                "ProviderName": "Cognito",
                "ProviderAttributeValue": native["Username"],
            },
            SourceUser={
                "ProviderName": "Google",
                "ProviderAttributeName": "Cognito_Subject",
                "ProviderAttributeValue": subject,
            },
        )
        logger.info("linked Google identity to invited user %s", native["Username"])
    except Exception:  # noqa: BLE001 - never block a sign-in on a linking failure
        logger.exception("pre-signup linking failed; continuing without link")
    return event
