"""Admin user management backed by Amazon Cognito admin APIs.

All operations target the configured Cognito user pool. Requires the ECS task
role to hold the relevant cognito-idp:Admin* permissions.
"""

from __future__ import annotations

import boto3
from fastapi import HTTPException, status

from neocloud.core.config import Settings
from neocloud.core.logging import get_logger
from neocloud.domains.admin.schemas import AdminUser

logger = get_logger(__name__)

# Internal Cognito groups we never surface/manage as assignable roles.
_HIDDEN_GROUPS = {"us-east-2_", "_Google"}


def _is_hidden_group(name: str) -> bool:
    return name.endswith("_Google") or "_Google" in name


class AdminService:
    def __init__(self, settings: Settings):
        if not settings.cognito_user_pool_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cognito user pool is not configured",
            )
        self._pool = settings.cognito_user_pool_id
        self._client = boto3.client("cognito-idp", region_name=settings.aws_region)

    # ---- helpers ---------------------------------------------------------- #
    @staticmethod
    def _attr(attrs: list[dict], key: str) -> str | None:
        for a in attrs:
            if a.get("Name") == key:
                return a.get("Value")
        return None

    def _groups_for(self, username: str) -> list[str]:
        resp = self._client.admin_list_groups_for_user(
            Username=username, UserPoolId=self._pool, Limit=60
        )
        return [
            g["GroupName"]
            for g in resp.get("Groups", [])
            if not _is_hidden_group(g["GroupName"])
        ]

    def _to_admin_user(self, u: dict, roles: list[str] | None = None) -> AdminUser:
        attrs = u.get("Attributes") or u.get("UserAttributes") or []
        username = u["Username"]
        return AdminUser(
            username=username,
            email=self._attr(attrs, "email"),
            name=self._attr(attrs, "name"),
            status=u.get("UserStatus", "UNKNOWN"),
            enabled=u.get("Enabled", True),
            created_at=(u["UserCreateDate"].isoformat() if u.get("UserCreateDate") else None),
            roles=roles if roles is not None else self._groups_for(username),
        )

    # ---- operations ------------------------------------------------------- #
    def list_users(self, limit: int = 60) -> list[AdminUser]:
        resp = self._client.list_users(UserPoolId=self._pool, Limit=limit)
        return [self._to_admin_user(u) for u in resp.get("Users", [])]

    def get_user(self, username: str) -> AdminUser:
        try:
            u = self._client.admin_get_user(UserPoolId=self._pool, Username=username)
        except self._client.exceptions.UserNotFoundException as exc:
            raise HTTPException(status_code=404, detail="User not found") from exc
        return self._to_admin_user(u)

    def invite_user(self, email: str, name: str | None, roles: list[str]) -> AdminUser:
        attrs = [
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
        ]
        if name:
            attrs.append({"Name": "name", "Value": name})
        try:
            # DesiredDeliveryMediums=EMAIL sends the Cognito invitation email with
            # a temporary password. The user completes signup / uses Google SSO.
            resp = self._client.admin_create_user(
                UserPoolId=self._pool,
                Username=email,
                UserAttributes=attrs,
                DesiredDeliveryMediums=["EMAIL"],
            )
        except self._client.exceptions.UsernameExistsException as exc:
            raise HTTPException(
                status_code=409, detail="A user with that email already exists"
            ) from exc
        for role in roles:
            self._add_to_group(email, role)
        logger.info("admin_user_invited", email=email, roles=roles)
        return self._to_admin_user(resp["User"], roles=roles)

    def set_roles(self, username: str, roles: list[str]) -> AdminUser:
        current = set(self._groups_for(username))
        desired = set(roles)
        for role in desired - current:
            self._add_to_group(username, role)
        for role in current - desired:
            self._client.admin_remove_user_from_group(
                UserPoolId=self._pool, Username=username, GroupName=role
            )
        logger.info("admin_user_roles_set", username=username, roles=sorted(desired))
        return self.get_user(username)

    def set_enabled(self, username: str, enabled: bool) -> AdminUser:
        if enabled:
            self._client.admin_enable_user(UserPoolId=self._pool, Username=username)
        else:
            self._client.admin_disable_user(UserPoolId=self._pool, Username=username)
        return self.get_user(username)

    def delete_user(self, username: str) -> None:
        try:
            self._client.admin_delete_user(UserPoolId=self._pool, Username=username)
        except self._client.exceptions.UserNotFoundException as exc:
            raise HTTPException(status_code=404, detail="User not found") from exc
        logger.info("admin_user_deleted", username=username)

    def _add_to_group(self, username: str, group: str) -> None:
        try:
            self._client.admin_add_user_to_group(
                UserPoolId=self._pool, Username=username, GroupName=group
            )
        except self._client.exceptions.ResourceNotFoundException as exc:
            raise HTTPException(
                status_code=400, detail=f"Unknown role/group: {group}"
            ) from exc
