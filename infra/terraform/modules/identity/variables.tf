variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "cognito_domain_prefix" {
  description = "Prefix for the Cognito hosted UI domain (globally unique in-region)."
  type        = string
}

variable "callback_urls" {
  description = "Allowed OAuth callback URLs."
  type        = list(string)
}

variable "logout_urls" {
  description = "Allowed logout URLs."
  type        = list(string)
}

variable "google_oidc_client_id" {
  description = "Google Workspace OIDC client ID."
  type        = string
  default     = ""
}

variable "google_oidc_client_secret" {
  description = "Google Workspace OIDC client secret."
  type        = string
  default     = ""
  sensitive   = true
}

variable "tags" {
  description = "Common tags."
  type        = map(string)
  default     = {}
}

variable "task_role_name" {
  description = "ECS task role name to attach Cognito admin permissions to (for the admin portal). Empty to skip."
  type        = string
  default     = ""
}
