variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "aurora_master_username" {
  description = "Aurora master username to store in Secrets Manager."
  type        = string
}

variable "google_oidc_client_id" {
  description = "Google Workspace OIDC client ID to store in Secrets Manager."
  type        = string
  default     = ""
}

variable "google_oidc_client_secret" {
  description = "Google Workspace OIDC client secret to store in Secrets Manager."
  type        = string
  default     = ""
  sensitive   = true
}

variable "tags" {
  description = "Common tags."
  type        = map(string)
  default     = {}
}
