variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "github_org" {
  description = "GitHub organization or user that owns the repo."
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name."
  type        = string
}

variable "github_subjects" {
  description = "List of OIDC subject patterns allowed to assume the role (e.g. 'ref:refs/heads/main', 'environment:production')."
  type        = list(string)
  default     = ["ref:refs/heads/main"]
}

variable "create_oidc_provider" {
  description = "Create the GitHub OIDC provider. Set false if one already exists in the account."
  type        = bool
  default     = true
}

variable "existing_oidc_provider_arn" {
  description = "ARN of an existing GitHub OIDC provider (used when create_oidc_provider is false)."
  type        = string
  default     = ""
}

variable "ecr_repository_arn" {
  description = "ARN of the ECR repository the pipeline may push to."
  type        = string
}

variable "passable_role_arns" {
  description = "ECS task and execution role ARNs the deploy role may pass."
  type        = list(string)
}

variable "tags" {
  description = "Common tags."
  type        = map(string)
  default     = {}
}
