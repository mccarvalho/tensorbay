"""Schemas for the admin user-management API."""

from pydantic import BaseModel, EmailStr, Field

from neocloud.auth.rbac import Role

# Roles an admin can assign through the portal. CUSTOMER_* are tenant roles
# managed elsewhere, but we expose all for completeness.
ASSIGNABLE_ROLES = [r.value for r in Role]


class AdminUser(BaseModel):
    username: str
    email: str | None = None
    name: str | None = None
    status: str
    enabled: bool
    created_at: str | None = None
    roles: list[str] = Field(default_factory=list)


class InviteUserRequest(BaseModel):
    email: EmailStr
    name: str | None = None
    roles: list[str] = Field(default_factory=list)


class UpdateRolesRequest(BaseModel):
    roles: list[str]


class RolesCatalog(BaseModel):
    roles: list[str]
