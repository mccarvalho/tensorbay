########################################
# Secrets Manager
########################################

# Random password for the Aurora master user.
resource "random_password" "aurora" {
  length           = 24
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "aurora" {
  name        = "${var.name_prefix}/aurora/master"
  description = "Aurora PostgreSQL master credentials for ${var.name_prefix}"
  kms_key_id  = aws_kms_key.secrets.arn
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "aurora" {
  secret_id = aws_secretsmanager_secret.aurora.id
  secret_string = jsonencode({
    username = var.aurora_master_username
    password = random_password.aurora.result
    engine   = "postgres"
    port     = 5432
  })
}

# Google Workspace OIDC client credentials used by Cognito federation.
# If values are not provided at apply time, a placeholder is stored and must be
# updated manually (console or CLI) before SSO will work.
resource "aws_secretsmanager_secret" "google_oidc" {
  name        = "${var.name_prefix}/sso/google-oidc"
  description = "Google Workspace OIDC client credentials for Cognito federation"
  kms_key_id  = aws_kms_key.secrets.arn
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "google_oidc" {
  secret_id = aws_secretsmanager_secret.google_oidc.id
  secret_string = jsonencode({
    client_id     = var.google_oidc_client_id
    client_secret = var.google_oidc_client_secret
  })
}
