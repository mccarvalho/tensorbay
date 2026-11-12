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

# Shared bearer token the website form backend presents to POST /v1/leads/ingest.
# Generated once here; ignore_changes lets it be rotated later with
# `aws secretsmanager put-secret-value` without Terraform reverting it.
resource "random_password" "lead_ingest" {
  length  = 48
  special = false
}

resource "aws_secretsmanager_secret" "lead_ingest" {
  name        = "${var.name_prefix}/leads/ingest-token"
  description = "Bearer token for the website lead-ingest webhook (${var.name_prefix})"
  kms_key_id  = aws_kms_key.secrets.arn
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "lead_ingest" {
  secret_id     = aws_secretsmanager_secret.lead_ingest.id
  secret_string = jsonencode({ token = random_password.lead_ingest.result })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Gmail sync (customer email -> activity timeline) connects mailboxes through
# Google OAuth, with no service-account key.
#
# 1) OAuth web client {"client_id","client_secret"}. Created empty; the values are
#    stored out-of-band with `aws secretsmanager put-secret-value` so they never
#    reach Terraform state, and ignore_changes stops Terraform reverting them.
#    While it is "{}" the email sync simply idles.
resource "aws_secretsmanager_secret" "gmail_oauth" {
  name        = "${var.name_prefix}/gmail/oauth-client"
  description = "Google OAuth web client for Gmail sync (${var.name_prefix})"
  kms_key_id  = aws_kms_key.secrets.arn
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "gmail_oauth" {
  secret_id     = aws_secretsmanager_secret.gmail_oauth.id
  secret_string = "{}"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# 2) Fernet key that encrypts the stored per-mailbox refresh tokens. Generated
#    once (256 random bits, url-safe base64) and never rotated by Terraform:
#    replacing it would make every stored token unreadable.
resource "random_id" "gmail_token_key" {
  byte_length = 32
}

resource "aws_secretsmanager_secret" "gmail_token_key" {
  name        = "${var.name_prefix}/gmail/token-key"
  description = "Encryption key for stored Gmail refresh tokens (${var.name_prefix})"
  kms_key_id  = aws_kms_key.secrets.arn
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "gmail_token_key" {
  secret_id     = aws_secretsmanager_secret.gmail_token_key.id
  secret_string = jsonencode({ key = random_id.gmail_token_key.b64_url })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
