import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from neocloud.common.auth import CurrentUser, require_permission
from neocloud.common.database import AsyncSession, get_db

router = APIRouter()


@router.get("/users")
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("admin.*"))],
):
    """List platform users."""
    ...


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("admin.*"))],
):
    """Create a platform user."""
    ...


@router.get("/roles")
async def list_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("admin.*"))],
):
    """List all roles."""
    ...


@router.post("/users/{user_id}/roles", status_code=status.HTTP_201_CREATED)
async def assign_role(
    user_id: uuid.UUID,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("admin.*"))],
):
    """Assign a role to a user."""
    ...


@router.delete("/users/{user_id}/roles/{role_id}")
async def revoke_role(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("admin.*"))],
):
    """Revoke a role from a user."""
    ...
