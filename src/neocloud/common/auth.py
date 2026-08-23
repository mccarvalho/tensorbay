import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()


@dataclass
class CurrentUser:
    id: uuid.UUID
    email: str
    user_type: str  # INTERNAL or CUSTOMER
    customer_id: uuid.UUID | None
    roles: list[str]
    permissions: list[str]


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> CurrentUser:
    """Validate JWT and return current user context.

    In production, this validates against Cognito JWKS.
    For development, it decodes a simple JWT.
    """
    token = credentials.credentials
    # TODO: Implement Cognito JWT validation
    # For now, extract from request state (set by middleware)
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return user


def require_permission(permission: str):
    """Dependency that checks if the current user has a specific permission."""

    async def _check(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if permission not in user.permissions and "admin.*" not in user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission}",
            )
        return user

    return _check


def require_tenant(customer_id_param: str = "customer_id"):
    """Dependency that enforces tenant isolation for customer users."""

    async def _check(
        user: Annotated[CurrentUser, Depends(get_current_user)],
        request: Request,
    ) -> CurrentUser:
        if user.user_type == "CUSTOMER":
            # Customer users can only access their own tenant
            path_customer_id = request.path_params.get(customer_id_param)
            if path_customer_id and str(user.customer_id) != path_customer_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: tenant isolation",
                )
        return user

    return _check
