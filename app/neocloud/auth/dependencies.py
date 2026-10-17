"""Cognito JWT validation and FastAPI auth dependencies."""

from dataclasses import dataclass, field

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError

from neocloud.auth.rbac import Permission, Role, permissions_for_roles
from neocloud.core.config import Settings, get_settings
from neocloud.core.logging import get_logger

logger = get_logger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)

# Cache JWKS keys per issuer for the process lifetime.
_jwks_cache: dict[str, dict] = {}


@dataclass
class CurrentUser:
    subject: str
    email: str | None
    roles: list[str] = field(default_factory=list)
    tenant_id: str | None = None
    permissions: set[Permission] = field(default_factory=set)

    def has_permission(self, perm: Permission) -> bool:
        return perm in self.permissions

    def is_customer(self) -> bool:
        return any(
            r in {Role.CUSTOMER_ADMIN, Role.CUSTOMER_USER} for r in self.roles
        )


async def _get_jwks(settings: Settings) -> dict:
    url = settings.cognito_jwks_url
    if not url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cognito not configured",
        )
    if url not in _jwks_cache:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            _jwks_cache[url] = resp.json()
    return _jwks_cache[url]


def _stub_user() -> CurrentUser:
    """Local/testing user with full access when auth is disabled."""
    roles = [Role.SUPER_ADMIN.value]
    return CurrentUser(
        subject="local-dev",
        email="dev@local",
        roles=roles,
        tenant_id=None,
        permissions=permissions_for_roles(roles),
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    if not settings.auth_enabled:
        return _stub_user()

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    token = credentials.credentials
    jwks = await _get_jwks(settings)

    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header["kid"]
        key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
        if key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unknown signing key",
            )
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=settings.cognito_issuer,
            options={"verify_aud": False},  # access tokens use client_id, not aud
        )
    except (JWTError, KeyError, StopIteration) as exc:
        logger.warning("jwt_validation_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    # Validate token_use and client.
    if claims.get("token_use") == "access":
        if settings.cognito_client_id and claims.get("client_id") != settings.cognito_client_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid client",
            )

    roles = claims.get("cognito:groups", []) or []
    return CurrentUser(
        subject=claims.get("sub", ""),
        email=claims.get("email"),
        roles=roles,
        tenant_id=claims.get("custom:tenant_id"),
        permissions=permissions_for_roles(roles),
    )


def require_permission(permission: Permission):
    """Dependency factory enforcing a specific permission."""

    async def _checker(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission.value}",
            )
        return user

    return _checker
