########################################
# Networking
########################################

output "vpc_id" {
  description = "VPC ID."
  value       = module.networking.vpc_id
}

output "public_subnet_ids" {
  value = module.networking.public_subnet_ids
}

output "app_subnet_ids" {
  value = module.networking.app_subnet_ids
}

output "data_subnet_ids" {
  value = module.networking.data_subnet_ids
}

########################################
# Compute
########################################

output "ecr_repository_url" {
  description = "Push the application image here."
  value       = module.compute.ecr_repository_url
}

output "ecs_cluster_name" {
  value = module.compute.ecs_cluster_name
}

output "ecs_service_name" {
  value = module.compute.ecs_service_name
}

output "alb_dns_name" {
  description = "Public endpoint of the platform API/UI."
  value       = module.compute.alb_dns_name
}

########################################
# Data
########################################

output "aurora_cluster_endpoint" {
  value = module.data.aurora_cluster_endpoint
}

output "aurora_reader_endpoint" {
  value = module.data.aurora_reader_endpoint
}

output "redis_primary_endpoint" {
  value = module.data.redis_primary_endpoint
}

########################################
# Security
########################################

output "aurora_secret_arn" {
  description = "Secrets Manager ARN with Aurora master credentials."
  value       = module.security.aurora_secret_arn
}

output "google_oidc_secret_arn" {
  description = "Secrets Manager ARN with Google OIDC client credentials."
  value       = module.security.google_oidc_secret_arn
}

########################################
# Identity (Cognito + Google SSO)
########################################

output "cognito_user_pool_id" {
  value = module.identity.user_pool_id
}

output "cognito_user_pool_client_id" {
  value = module.identity.user_pool_client_id
}

output "cognito_hosted_ui_url" {
  description = "Base URL of the Cognito hosted login UI."
  value       = module.identity.hosted_ui_url
}

output "google_idp_redirect_uri" {
  description = "Register this exact URI as an Authorized redirect URI in the Google OAuth client."
  value       = module.identity.google_idp_redirect_uri
}

########################################
# Messaging & observability
########################################

output "event_bus_name" {
  value = module.observability.event_bus_name
}

output "cloudwatch_dashboard" {
  value = module.observability.dashboard_name
}

########################################
# Storage
########################################

output "data_bucket_name" {
  value = aws_s3_bucket.data.bucket
}

########################################
# AI document generation
########################################

output "bedrock_model_id" {
  description = "Bedrock model/inference profile used for MSA/LOI/Proposal/Contract generation."
  value       = module.ai.bedrock_model_id
}

output "bedrock_guardrail_id" {
  description = "Bedrock Guardrail ID for document generation."
  value       = module.ai.guardrail_id
}

########################################
# CI/CD
########################################

output "cicd_deploy_role_arn" {
  description = "GitHub Actions deploy role ARN (set as AWS_DEPLOY_ROLE_ARN in GitHub). Empty if CI/CD disabled."
  value       = var.enable_cicd ? module.cicd[0].deploy_role_arn : ""
}
