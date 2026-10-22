variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "account_id" {
  description = "AWS account ID (used to scope the SES->SNS publish policy)."
  type        = string
}

variable "notification_email" {
  description = "Email address to notify on SES bounce/complaint events. Empty disables the subscription."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Common tags."
  type        = map(string)
  default     = {}
}
