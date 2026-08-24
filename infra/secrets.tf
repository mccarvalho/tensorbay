# =============================================================================
# NeoCloud Secrets Manager Structure
# =============================================================================
#
# Naming convention: neocloud/{environment}/{service}/{credential}
#
# Environments: dev | staging | prod
# Services: db | redis | app | cognito | integrations | cicd
#
# =============================================================================

# ---- Database ----------------------------------------------------------------

resource "aws_secretsmanager_secret" "db_master" {
  name                    = "neocloud/${var.environment}/db/master"
  description             = "PostgreSQL master credentials"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = { Service = "database", Sensitivity = "critical" }
}

resource "aws_secretsmanager_secret_version" "db_master" {
  secret_id = aws_secretsmanager_secret.db_master.id
  secret_string = jsonencode({
    host     = aws_db_instance.main.address
    port     = 5432
    dbname   = var.db_name
    username = "neocloud"
    password = random_password.db_password.result
    url      = "postgresql+asyncpg://neocloud:${random_password.db_password.result}@${aws_db_instance.main.address}:5432/${var.db_name}"
  })
}

# ---- Application Config ------------------------------------------------------

resource "aws_secretsmanager_secret" "app_config" {
  name                    = "neocloud/${var.environment}/app/config"
  description             = "Application configuration secrets (JWT signing key, encryption keys)"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = { Service = "app", Sensitivity = "critical" }
}

resource "random_password" "jwt_secret" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret_version" "app_config" {
  secret_id = aws_secretsmanager_secret.app_config.id
  secret_string = jsonencode({
    jwt_secret_key    = random_password.jwt_secret.result
    jwt_algorithm     = "HS256"
    encryption_key    = random_password.jwt_secret.result  # Override in prod with KMS-derived key
    cors_origins      = var.environment == "prod" ? "" : "*"
    app_env           = var.environment
    app_debug         = var.environment != "prod" ? "true" : "false"
  })
}

# ---- Cognito -----------------------------------------------------------------

resource "aws_secretsmanager_secret" "cognito" {
  name                    = "neocloud/${var.environment}/cognito/config"
  description             = "Cognito user pool and client credentials"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = { Service = "cognito", Sensitivity = "high" }
}

resource "aws_secretsmanager_secret_version" "cognito" {
  secret_id = aws_secretsmanager_secret.cognito.id
  secret_string = jsonencode({
    user_pool_id = aws_cognito_user_pool.main.id
    client_id    = aws_cognito_user_pool_client.api.id
    region       = var.aws_region
    jwks_url     = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}/.well-known/jwks.json"
  })
}

# ---- Infrastructure References -----------------------------------------------

resource "aws_secretsmanager_secret" "infra_config" {
  name                    = "neocloud/${var.environment}/infra/config"
  description             = "Infrastructure endpoints (Redis, S3, EventBridge)"
  recovery_window_in_days = 0

  tags = { Service = "infra", Sensitivity = "low" }
}

resource "aws_secretsmanager_secret_version" "infra_config" {
  secret_id = aws_secretsmanager_secret.infra_config.id
  secret_string = jsonencode({
    redis_url        = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:6379/0"
    s3_bucket        = aws_s3_bucket.documents.id
    eventbridge_bus  = aws_cloudwatch_event_bus.main.name
    aws_region       = var.aws_region
    ecs_cluster      = aws_ecs_cluster.main.name
    ecr_repository   = aws_ecr_repository.api.repository_url
  })
}

# ---- Third-party Integrations ------------------------------------------------
# These are created empty and filled manually (CRM, ERP, payment processors)

resource "aws_secretsmanager_secret" "integrations_crm" {
  name                    = "neocloud/${var.environment}/integrations/crm"
  description             = "CRM integration credentials (Salesforce/HubSpot)"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = { Service = "integrations", Sensitivity = "high" }
}

resource "aws_secretsmanager_secret" "integrations_erp" {
  name                    = "neocloud/${var.environment}/integrations/erp"
  description             = "ERP/accounting system credentials"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = { Service = "integrations", Sensitivity = "high" }
}

resource "aws_secretsmanager_secret" "integrations_smtp" {
  name                    = "neocloud/${var.environment}/integrations/smtp"
  description             = "SMTP / email service credentials"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = { Service = "integrations", Sensitivity = "medium" }
}

# ---- Outputs -----------------------------------------------------------------

output "secret_arns" {
  description = "ARNs of all managed secrets"
  value = {
    db_master    = aws_secretsmanager_secret.db_master.arn
    app_config   = aws_secretsmanager_secret.app_config.arn
    cognito      = aws_secretsmanager_secret.cognito.arn
    infra_config = aws_secretsmanager_secret.infra_config.arn
    integrations = {
      crm  = aws_secretsmanager_secret.integrations_crm.arn
      erp  = aws_secretsmanager_secret.integrations_erp.arn
      smtp = aws_secretsmanager_secret.integrations_smtp.arn
    }
  }
  sensitive = true
}
