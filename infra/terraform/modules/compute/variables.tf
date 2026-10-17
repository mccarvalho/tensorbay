variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "aws_region" {
  description = "AWS region (used for log configuration)."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for the ALB."
  type        = list(string)
}

variable "app_subnet_ids" {
  description = "Private app subnet IDs for the Fargate tasks."
  type        = list(string)
}

variable "alb_security_group_id" {
  description = "Security group for the ALB."
  type        = string
}

variable "ecs_security_group_id" {
  description = "Security group for the ECS tasks."
  type        = string
}

variable "alb_internal" {
  description = "Whether the ALB is internal."
  type        = bool
  default     = false
}

variable "container_image" {
  description = "Container image for the application."
  type        = string
}

variable "container_port" {
  description = "Application container port."
  type        = number
}

variable "service_desired_count" {
  description = "Desired number of Fargate tasks."
  type        = number
}

variable "task_cpu" {
  description = "Fargate task CPU units."
  type        = number
}

variable "task_memory" {
  description = "Fargate task memory (MiB)."
  type        = number
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention in days."
  type        = number
  default     = 30
}

variable "kms_logs_key_arn" {
  description = "KMS key ARN for CloudWatch Logs encryption."
  type        = string
}

variable "waf_web_acl_arn" {
  description = "WAF Web ACL ARN to associate with the ALB."
  type        = string
}

variable "secret_arns" {
  description = "List of Secrets Manager ARNs the task role may read."
  type        = list(string)
  default     = []
}

variable "secrets_kms_key_arn" {
  description = "KMS key ARN used to encrypt the secrets; task/exec roles need kms:Decrypt on it."
  type        = string
  default     = ""
}

variable "environment_variables" {
  description = "Plain (non-secret) environment variables to inject into the container."
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Common tags."
  type        = map(string)
  default     = {}
}
