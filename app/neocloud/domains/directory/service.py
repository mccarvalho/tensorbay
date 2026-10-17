"""Directory lookups backed by Amazon Cognito (read-only, minimal fields)."""

from __future__ import annotations

import boto3
from fastapi import HTTPException, status

from neocloud.core.config import Settings
from neocloud.domains.directory.schemas import DirectoryUser


class DirectoryService:
    def __init__(self, settings: Settings):
        if not settings.cognito_user_pool_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cognito user pool is not configured",
            )
        self._pool = settings.cognito_user_pool_id
        self._client = boto3.client("cognito-idp", region_name=settings.aws_region)

    @staticmethod
    def _attr(attrs: list[dict], key: str) -> str | None:
        for a in attrs:
            if a.get("Name") == key:
                return a.get("Value")
        return None

    def list_users(self, q: str | None = None, limit: int = 60) -> list[DirectoryUser]:
        """Return enabled users as {sub, email, name}.

        Optional ``q`` filters (case-insensitive) on name or email. Cognito's
        server-side filter only matches a single prefix attribute, so we fetch
        and filter in-process to search both fields and allow substrings.
        """
        resp = self._client.list_users(UserPoolId=self._pool, Limit=60)
        out: list[DirectoryUser] = []
        needle = q.strip().lower() if q else None
        for u in resp.get("Users", []):
            if not u.get("Enabled", True):
                continue
            attrs = u.get("Attributes") or u.get("UserAttributes") or []
            sub = self._attr(attrs, "sub") or u.get("Username", "")
            email = self._attr(attrs, "email")
            name = self._attr(attrs, "name")
            if needle:
                hay = f"{name or ''} {email or ''}".lower()
                if needle not in hay:
                    continue
            out.append(DirectoryUser(sub=sub, email=email, name=name))
        # Stable, human-friendly ordering by display name then email.
        out.sort(key=lambda d: (d.name or d.email or "").lower())
        return out[:limit]
