# Grants the ECS task role the Cognito admin permissions needed by the in-app
# admin portal (invite users, manage group/role membership, enable/disable,
# delete). Scoped to this user pool only.

resource "aws_iam_role_policy" "task_cognito_admin" {
  count = var.task_role_name != "" ? 1 : 0
  name  = "${var.name_prefix}-cognito-admin"
  role  = var.task_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cognito-idp:ListUsers",
          "cognito-idp:AdminGetUser",
          "cognito-idp:AdminCreateUser",
          "cognito-idp:AdminDeleteUser",
          "cognito-idp:AdminEnableUser",
          "cognito-idp:AdminDisableUser",
          "cognito-idp:AdminListGroupsForUser",
          "cognito-idp:AdminAddUserToGroup",
          "cognito-idp:AdminRemoveUserFromGroup",
          "cognito-idp:ListGroups"
        ]
        Resource = aws_cognito_user_pool.this.arn
      }
    ]
  })
}
