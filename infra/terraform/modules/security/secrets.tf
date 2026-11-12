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

# Google service-account key (JSON) used to read Gmail with domain-wide
# delegation (customer email -> activity timeline). Created empty: the real key is
# stored out-of-band with `aws secretsmanager put-secret-value`, never in Terraform
# state, and ignore_changes keeps Terraform from reverting it. While it is "{}" the
# email sync simply idles.
resource "aws_secretsmanager_secret" "gmail_sa" {
  name        = "${var.name_prefix}/gmail/service-account"
  description = "Google service-account key for Gmail sync (${var.name_prefix})"
  kms_key_id  = aws_kms_key.secrets.arn
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "gmail_sa" {
  secret_id     = aws_secretsmanager_secret.gmail_sa.id
  secret_string = "{}"

  lifecycle {
    ignore_changes = [secret_string]
  }
}
