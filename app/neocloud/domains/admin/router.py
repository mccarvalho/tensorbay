"""Admin API: user invitation and role management (SUPER_ADMIN only).

Backed by Amazon Cognito. Every write is recorded in the audit trail. Guarded by
the USER_ADMIN permission, which only SUPER_ADMIN holds.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.core.config import Settings, get_settings
from neocloud.db.session import get_session
from neocloud.domains.admin.schemas import (
    ASSIGNABLE_ROLES,
    AdminUser,
    InviteUserRequest,
    RolesCatalog,
    UpdateRolesRequest,
)
from neocloud.domains.admin.service import AdminService

router = APIRouter(prefix="/admin", tags=["Admin"])

ENTITY_USER = "cognito_user"


def _service(settings: Settings = Depends(get_settings)) -> AdminService:
    return AdminService(settings)


@router.get("/roles", response_model=RolesCatalog)
async def list_roles(
    _: CurrentUser = Depends(require_permission(Permission.USER_ADMIN)),
) -> RolesCatalog:
    """The roles an administrator can assign."""
    return RolesCatalog(roles=ASSIGNABLE_ROLES)


@router.get("/users", response_model=list[AdminUser])
async def list_users(
    limit: int = Query(60, ge=1, le=60),
    _: CurrentUser = Depends(require_permission(Permission.USER_ADMIN)),
    service: AdminService = Depends(_service),
) -> list[AdminUser]:
    return service.list_users(limit=limit)


@router.get("/users/{username}", response_model=AdminUser)
async def get_user(
    username: str,
    _: CurrentUser = Depends(require_permission(Permission.USER_ADMIN)),
    service: AdminService = Depends(_service),
) -> AdminUser:
    return service.get_user(username)


@router.post("/users", response_model=AdminUser, status_code=status.HTTP_201_CREATED)
async def invite_user(
    payload: InviteUserRequest,
    user: CurrentUser = Depends(require_permission(Permission.USER_ADMIN)),
    service: AdminService = Depends(_service),
    session: AsyncSession = Depends(get_session),
) -> AdminUser:
    created = service.invite_user(payload.email, payload.name, payload.roles)
    await record_audit(
        session,
        action="invite",
        entity_type=ENTITY_USER,
        entity_id=created.username,
        actor=user.subject,
        new_value={"email": payload.email, "roles": payload.roles},
    )
    await session.commit()
    return created


@router.put("/users/{username}/roles", response_model=AdminUser)
async def set_roles(
    username: str,
    payload: UpdateRolesRequest,
    user: CurrentUser = Depends(require_permission(Permission.USER_ADMIN)),
    service: AdminService = Depends(_service),
    session: AsyncSession = Depends(get_session),
) -> AdminUser:
    before = service.get_user(username)
    updated = service.set_roles(username, payload.roles)
    await record_audit(
        session,
        action="set_roles",
        entity_type=ENTITY_USER,
        entity_id=username,
        actor=user.subject,
        old_value={"roles": before.roles},
        new_value={"roles": updated.roles},
    )
    await session.commit()
    return updated


@router.post("/users/{username}/enable", response_model=AdminUser)
async def enable_user(
    username: str,
    user: CurrentUser = Depends(require_permission(Permission.USER_ADMIN)),
    service: AdminService = Depends(_service),
    session: AsyncSession = Depends(get_session),
) -> AdminUser:
    updated = service.set_enabled(username, True)
    await record_audit(
        session, action="enable", entity_type=ENTITY_USER,
        entity_id=username, actor=user.subject,
    )
    await session.commit()
    return updated


@router.post("/users/{username}/disable", response_model=AdminUser)
async def disable_user(
    username: str,
    user: CurrentUser = Depends(require_permission(Permission.USER_ADMIN)),
    service: AdminService = Depends(_service),
    session: AsyncSession = Depends(get_session),
) -> AdminUser:
    updated = service.set_enabled(username, False)
    await record_audit(
        session, action="disable", entity_type=ENTITY_USER,
        entity_id=username, actor=user.subject,
    )
    await session.commit()
    return updated


@router.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    username: str,
    user: CurrentUser = Depends(require_permission(Permission.USER_ADMIN)),
    service: AdminService = Depends(_service),
    session: AsyncSession = Depends(get_session),
) -> None:
    service.delete_user(username)
    await record_audit(
        session, action="delete", entity_type=ENTITY_USER,
        entity_id=username, actor=user.subject,
    )
    await session.commit()
