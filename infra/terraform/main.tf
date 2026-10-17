########################################
# NeoCloud Platform - Release 1 Foundation
# Root module wiring all foundation modules together.
########################################

module "networking" {
  source = "./modules/networking"

  name_prefix        = local.name_prefix
  vpc_cidr           = var.vpc_cidr
  azs                = local.azs
  single_nat_gateway = var.single_nat_gateway
  container_port     = var.container_port
  tags               = local.common_tags
}

module "security" {
  source = "./modules/security"

  name_prefix               = local.name_prefix
  aurora_master_username    = var.aurora_master_username
  google_oidc_client_id     = var.google_oidc_client_id
  google_oidc_client_secret = var.google_oidc_client_secret
  tags                      = local.common_tags
}

module "data" {
  source = "./modules/data"

  name_prefix              = local.name_prefix
  data_subnet_ids          = module.networking.data_subnet_ids
  aurora_security_group_id = module.networking.aurora_security_group_id
  redis_security_group_id  = module.networking.redis_security_group_id
  kms_rds_key_arn          = module.security.kms_rds_key_arn

  aurora_engine_version  = var.aurora_engine_version
  aurora_database_name   = var.aurora_database_name
  aurora_master_username = var.aurora_master_username
  aurora_master_password = module.security.aurora_password
  aurora_min_capacity    = var.aurora_min_capacity
  aurora_max_capacity    = var.aurora_max_capacity

  redis_node_type          = var.redis_node_type
  redis_num_cache_clusters = var.redis_num_cache_clusters

  tags = local.common_tags
}

module "compute" {
  source = "./modules/compute"

  name_prefix           = local.name_prefix
  aws_region            = var.aws_region
  vpc_id                = module.networking.vpc_id
  public_subnet_ids     = module.networking.public_subnet_ids
  app_subnet_ids        = module.networking.app_subnet_ids
  alb_security_group_id = module.networking.alb_security_group_id
  ecs_security_group_id = module.networking.ecs_security_group_id
  alb_internal          = var.alb_internal

  container_image       = var.container_image
  container_port        = var.container_port
  service_desired_count = var.service_desired_count
  task_cpu              = var.task_cpu
  task_memory           = var.task_memory

  log_retention_days = var.log_retention_days
  kms_logs_key_arn   = module.security.kms_logs_key_arn
  waf_web_acl_arn    = module.security.waf_web_acl_arn

  # Let the task read DB and SSO secrets.
  secret_arns = [
    module.security.aurora_secret_arn,
    module.security.google_oidc_secret_arn
  ]
  secrets_kms_key_arn = module.security.kms_secrets_key_arn

  # Non-secret runtime config injected into the container.
  environment_variables = {
    APP_ENV               = var.environment
    AWS_REGION            = var.aws_region
    BEDROCK_MODEL_ID      = var.bedrock_model_id
    DOCUMENTS_BUCKET      = aws_s3_bucket.data.bucket
    AURORA_SECRET_ARN     = module.security.aurora_secret_arn
    AURORA_HOST           = module.data.aurora_cluster_endpoint
    AURORA_DATABASE       = var.aurora_database_name
    GOOGLE_SSO_SECRET_ARN = module.security.google_oidc_secret_arn
    COGNITO_USER_POOL_ID  = module.identity.user_pool_id
    COGNITO_CLIENT_ID     = module.identity.user_pool_client_id
  }

  tags = local.common_tags
}

module "identity" {
  source = "./modules/identity"

  name_prefix               = local.name_prefix
  cognito_domain_prefix     = var.cognito_domain_prefix
  callback_urls             = var.cognito_callback_urls
  logout_urls               = var.cognito_logout_urls
  google_oidc_client_id     = var.google_oidc_client_id
  google_oidc_client_secret = var.google_oidc_client_secret
  task_role_name            = module.compute.task_role_name
  tags                      = local.common_tags
}

module "observability" {
  source = "./modules/observability"

  name_prefix      = local.name_prefix
  aws_region       = var.aws_region
  ecs_cluster_name = module.compute.ecs_cluster_name
  ecs_service_name = module.compute.ecs_service_name
  alb_arn_suffix   = module.compute.alb_arn_suffix
  alarm_email      = var.alarm_email
  tags             = local.common_tags
}

########################################
# S3 bucket for platform / metering data (section 24)
########################################

resource "aws_s3_bucket" "data" {
  bucket = "${local.name_prefix}-data-${data.aws_caller_identity.current.account_id}"
  tags   = local.common_tags
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = module.security.kms_s3_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

########################################
# AI document generation (Amazon Bedrock)
########################################

module "ai" {
  source = "./modules/ai"

  name_prefix          = local.name_prefix
  aws_region           = var.aws_region
  account_id           = data.aws_caller_identity.current.account_id
  bedrock_model_id     = var.bedrock_model_id
  enable_guardrail     = var.bedrock_enable_guardrail
  task_role_name       = module.compute.task_role_name
  documents_bucket_arn = aws_s3_bucket.data.arn
  tags                 = local.common_tags
}

########################################
# CI/CD (GitHub Actions OIDC) - optional
########################################

module "cicd" {
  source = "./modules/cicd"
  count  = var.enable_cicd ? 1 : 0

  name_prefix          = local.name_prefix
  github_org           = var.github_org
  github_repo          = var.github_repo
  github_subjects      = var.github_subjects
  sub_patterns         = var.github_sub_patterns
  create_oidc_provider = var.github_create_oidc_provider
  ecr_repository_arn   = module.compute.ecr_repository_arn
  passable_role_arns = [
    module.compute.task_role_arn,
    module.compute.execution_role_arn,
  ]
  frontend_bucket_arn       = module.frontend.bucket_arn
  frontend_distribution_arn = module.frontend.distribution_arn
  tags                      = local.common_tags
}

########################################
# Frontend hosting (S3 + CloudFront)
########################################

module "frontend" {
  source = "./modules/frontend"

  name_prefix       = local.name_prefix
  api_origin_domain = module.compute.alb_dns_name
  tags              = local.common_tags
}
