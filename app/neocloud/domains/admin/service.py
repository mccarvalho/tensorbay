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
        self._settings = settings
        self._client = boto3.client("cognito-idp", region_name=settings.aws_region)
        self._ses = boto3.client("ses", region_name=settings.aws_region)

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

        # Google-SSO-only: we do NOT use Cognito's native invite email (it always
        # carries a temporary password). Instead, when a verified SES sender is
        # configured, suppress Cognito's email and send our own branded,
        # password-free "access granted — sign in with Google" message. If SES is
        # not configured, fall back to Cognito's email so invites still work.
        use_ses = bool(self._settings.ses_from_email)
        create_kwargs: dict = {
            "UserPoolId": self._pool,
            "Username": email,
            "UserAttributes": attrs,
        }
        if use_ses:
            create_kwargs["MessageAction"] = "SUPPRESS"
        else:
            create_kwargs["DesiredDeliveryMediums"] = ["EMAIL"]
        try:
            resp = self._client.admin_create_user(**create_kwargs)
        except self._client.exceptions.UsernameExistsException as exc:
            raise HTTPException(
                status_code=409, detail="A user with that email already exists"
            ) from exc
        for role in roles:
            self._add_to_group(email, role)
        if use_ses:
            self._send_invite_email(email, name)
        logger.info(
            "admin_user_invited", email=email, roles=roles, via="ses" if use_ses else "cognito"
        )
        return self._to_admin_user(resp["User"], roles=roles)

    def _send_invite_email(self, email: str, name: str | None) -> None:
        """Send the branded, password-free access-granted email via SES."""
        login_url = self._settings.app_base_url
        greeting = f"Hi {name}," if name else "Hi,"
        subject = "Welcome to TensorBay GPU Control Plane"
        html = f"""\
<div style="margin:0;padding:0;background:#0D0221;font-family:Inter,Segoe UI,Arial,sans-serif;">
  <div style="max-width:520px;margin:0 auto;padding:32px 24px;">
    <div style="text-align:center;margin-bottom:24px;">
      <div style="font-size:20px;font-weight:800;color:#ffffff;letter-spacing:0.5px;">TensorBay</div>
      <div style="font-size:11px;letter-spacing:3px;color:#B9A9D6;text-transform:uppercase;margin-top:4px;">GPU Control Plane</div>
    </div>
    <div style="background:#1a0a3a;border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:28px;">
      <h1 style="margin:0 0 12px;font-size:20px;color:#ffffff;">You've been granted access</h1>
      <p style="margin:0 0 20px;font-size:14px;line-height:1.6;color:#B9A9D6;">
        {greeting} your TensorBay Google account <strong style="color:#ffffff;">{email}</strong>
        now has access to the TensorBay GPU Control Plane. Just sign in with Google —
        there's no password to set.
      </p>
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:4px 0;">
        <tr>
          <td align="center" bgcolor="#00D4FF" style="background-color:#00D4FF;background:linear-gradient(90deg,#00D4FF,#B165FB);border-radius:12px;">
            <a href="{login_url}"
               style="display:block;text-align:center;color:#0D0221;font-weight:700;text-decoration:none;padding:14px 20px;font-size:15px;font-family:Inter,Segoe UI,Arial,sans-serif;">
              Sign in with Google &rarr;
            </a>
          </td>
        </tr>
      </table>
    </div>
    <p style="text-align:center;font-size:11px;color:rgba(185,169,214,0.5);margin-top:24px;">
      TensorBay GPU Control Plane &middot; If you didn't expect this, you can ignore this email.
    </p>
  </div>
</div>"""
        text = (
            f"{greeting}\n\nYour TensorBay Google account {email} now has access to the "
            f"TensorBay GPU Control Plane. Sign in with Google (no password needed):\n"
            f"{login_url}\n\nIf you didn't expect this, you can ignore this email."
        )
        try:
            send_kwargs: dict = {
                "Source": self._settings.ses_from_email,
                "Destination": {"ToAddresses": [email]},
                "Message": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": html, "Charset": "UTF-8"},
                        "Text": {"Data": text, "Charset": "UTF-8"},
                    },
                },
            }
            if self._settings.ses_configuration_set:
                send_kwargs["ConfigurationSetName"] = self._settings.ses_configuration_set
            self._ses.send_email(**send_kwargs)
            logger.info("invite_email_sent", email=email)
        except Exception as exc:  # noqa: BLE001 — don't fail the invite on email error
            logger.error("invite_email_failed", email=email, error=str(exc))

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
