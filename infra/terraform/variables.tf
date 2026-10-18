variable "aws_region" {
  description = "AWS region to deploy the NeoCloud Platform foundation."
  type        = string
  default     = "us-east-2"
}

variable "project_name" {
  description = "Project name used as a prefix for resource naming and tags."
  type        = string
  default     = "neocloud"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

############################
# Networking
############################

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "az_count" {
  description = "Number of Availability Zones to span (2 recommended for dev)."
  type        = number
  default     = 2

  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "az_count must be between 2 and 3."
  }
}

variable "single_nat_gateway" {
  description = "Use a single NAT gateway (cheaper, dev) instead of one per AZ (HA)."
  type        = bool
  default     = true
}

############################
# Data layer
############################

variable "aurora_engine_version" {
  description = "Aurora PostgreSQL engine version."
  type        = string
  default     = "17.11"
}

variable "aurora_min_capacity" {
  description = "Aurora Serverless v2 minimum ACU."
  type        = number
  default     = 0.5
}

variable "aurora_max_capacity" {
  description = "Aurora Serverless v2 maximum ACU."
  type        = number
  default     = 4
}

variable "aurora_database_name" {
  description = "Initial database name created in the Aurora cluster."
  type        = string
  default     = "neocloud"
}

variable "aurora_master_username" {
  description = "Master username for the Aurora cluster."
  type        = string
  default     = "neocloud_admin"
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type."
  type        = string
  default     = "cache.t4g.micro"
}

variable "redis_num_cache_clusters" {
  description = "Number of Redis nodes (>=2 enables Multi-AZ)."
  type        = number
  default     = 2
}

############################
# Compute (ECS Fargate)
############################

variable "container_image" {
  description = "Container image for the FastAPI modular monolith. Defaults to a placeholder until the app image is pushed to ECR."
  type        = string
  default     = "public.ecr.aws/docker/library/nginx:latest"
}

variable "container_port" {
  description = "Port the application container listens on."
  type        = number
  default     = 8000
}

variable "service_desired_count" {
  description = "Desired number of Fargate tasks."
  type        = number
  default     = 2
}

variable "task_cpu" {
  description = "Fargate task CPU units (256 = 0.25 vCPU)."
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 1024
}

variable "alb_internal" {
  description = "Whether the ALB is internal (true) or internet-facing (false)."
  type        = bool
  default     = false
}

############################
# Identity (Cognito + Google Workspace SSO)
############################

variable "google_oidc_client_id" {
  description = "Google Workspace OAuth 2.0 Client ID for Cognito federation. Create it in Google Cloud Console (APIs & Services > Credentials)."
  type        = string
  default     = ""
}

variable "google_oidc_client_secret" {
  description = "Google Workspace OAuth 2.0 Client Secret. Leave empty to populate the Secrets Manager entry manually after apply."
  type        = string
  default     = ""
  sensitive   = true
}

variable "cognito_callback_urls" {
  description = "Allowed OAuth callback URLs for the Cognito app client (e.g., frontend and local dev URLs)."
  type        = list(string)
  default     = ["https://localhost:3000/callback"]
}

variable "cognito_logout_urls" {
  description = "Allowed logout URLs for the Cognito app client."
  type        = list(string)
  default     = ["https://localhost:3000/logout"]
}

variable "cognito_domain_prefix" {
  description = "Prefix for the Cognito hosted UI domain. Must be globally unique within the region."
  type        = string
  default     = "neocloud-dev-auth"
}

############################
# Observability
############################

variable "log_retention_days" {
  description = "CloudWatch Logs retention in days."
  type        = number
  default     = 30
}

variable "alarm_email" {
  description = "Email address to subscribe to the CloudWatch alarm SNS topic. Leave empty to skip subscription."
  type        = string
  default     = ""
}

variable "ses_from_email" {
  description = "Verified SES sender for invite/notification emails. Empty = fall back to Cognito's native invite (with temp password)."
  type        = string
  default     = ""
}

variable "app_base_url" {
  description = "Public base URL of the frontend, used in invite emails (Sign in with Google link)."
  type        = string
  default     = "https://d22xy9yyfwju3n.cloudfront.net"
}

############################
# AI document generation (Amazon Bedrock)
############################

variable "bedrock_model_id" {
  description = "Bedrock model ID or cross-region inference profile used for AI document generation (MSA/LOI/Proposal/Contract). Models in us-east-2 require an inference profile."
  type        = string
  default     = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "bedrock_enable_guardrail" {
  description = "Whether to create a Bedrock Guardrail for the document-generation feature."
  type        = bool
  default     = true
}

############################
# CI/CD (GitHub Actions OIDC)
############################

variable "enable_cicd" {
  description = "Create the GitHub Actions OIDC provider and deploy role."
  type        = bool
  default     = false
}

variable "github_org" {
  description = "GitHub organization/user that owns the repository."
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "GitHub repository name for the NeoCloud app."
  type        = string
  default     = ""
}

variable "github_create_oidc_provider" {
  description = "Create the GitHub OIDC provider (set false if it already exists in the account)."
  type        = bool
  default     = true
}

variable "github_subjects" {
  description = "OIDC subject patterns allowed to assume the deploy role (e.g. 'ref:refs/heads/main', 'environment:dev')."
  type        = list(string)
  default     = ["ref:refs/heads/main"]
}

variable "github_sub_patterns" {
  description = "Full verbatim OIDC sub StringLike patterns (needed for GitHub's immutable-ID subject format). If empty, github_subjects is used."
  type        = list(string)
  default     = []
}
