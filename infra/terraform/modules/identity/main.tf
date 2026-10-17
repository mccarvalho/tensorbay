########################################
# Cognito User Pool
########################################

data "aws_region" "current" {}

resource "aws_cognito_user_pool" "this" {
  name = "${var.name_prefix}-users"

  # Email is the primary attribute (federated identities map email in).
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  mfa_configuration = "OPTIONAL"
  software_token_mfa_configuration {
    enabled = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = var.tags
}

########################################
# Google Workspace federation (OIDC)
#
# Uses Google as an OIDC identity provider. Create an OAuth 2.0 Client ID in the
# Google Cloud Console (type "Web application"), restrict the OAuth consent screen
# to your Workspace organization, and set the authorized redirect URI to:
#   https://<cognito_domain_prefix>.auth.<region>.amazoncognito.com/oauth2/idpresponse
########################################

resource "aws_cognito_identity_provider" "google" {
  count = var.google_oidc_client_id != "" ? 1 : 0

  user_pool_id  = aws_cognito_user_pool.this.id
  provider_name = "Google"
  provider_type = "Google"

  provider_details = {
    client_id        = var.google_oidc_client_id
    client_secret    = var.google_oidc_client_secret
    authorize_scopes = "openid email profile"
  }

  # Map Google claims to Cognito user attributes.
  attribute_mapping = {
    email          = "email"
    email_verified = "email_verified"
    name           = "name"
    username       = "sub"
  }
}

########################################
# Hosted UI domain
########################################

resource "aws_cognito_user_pool_domain" "this" {
  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.this.id
}

########################################
# App client (used by the web frontend / API)
########################################

resource "aws_cognito_user_pool_client" "web" {
  name         = "${var.name_prefix}-web-client"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret = false

  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid", "email", "profile"]

  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls

  # Enable Google federation plus native Cognito users.
  supported_identity_providers = concat(
    ["COGNITO"],
    var.google_oidc_client_id != "" ? ["Google"] : []
  )

  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_ADMIN_USER_PASSWORD_AUTH"
  ]

  access_token_validity  = 60
  id_token_validity      = 60
  refresh_token_validity = 30
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  depends_on = [aws_cognito_identity_provider.google]
}

########################################
# RBAC groups (section 20 of the product plan)
########################################

locals {
  rbac_roles = {
    SUPER_ADMIN        = { precedence = 1, description = "Full platform administration" }
    EXECUTIVE          = { precedence = 10, description = "Executive dashboards and reporting" }
    SALES_MANAGER      = { precedence = 20, description = "Sales management, pipeline, pricing, contracts" }
    SALES              = { precedence = 30, description = "Commercialization: availability, quotes, reservations" }
    FINANCE            = { precedence = 40, description = "Billing, commitments, credits, margin" }
    OPERATIONS_MANAGER = { precedence = 50, description = "Infrastructure operations management" }
    OPERATIONS         = { precedence = 60, description = "NOC/infrastructure operations" }
    CLOUD_ADMIN        = { precedence = 70, description = "Allocation, provisioning, operations" }
    CUSTOMER_ADMIN     = { precedence = 80, description = "Customer tenant administration" }
    CUSTOMER_USER      = { precedence = 90, description = "Customer end user: instances, usage" }
  }
}

resource "aws_cognito_user_group" "rbac" {
  for_each = local.rbac_roles

  name         = each.key
  user_pool_id = aws_cognito_user_pool.this.id
  description  = each.value.description
  precedence   = each.value.precedence
}
