variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "aws_region" {
  description = "AWS region (for ARN construction)."
  type        = string
}

variable "account_id" {
  description = "AWS account ID (for ARN construction)."
  type        = string
}

variable "bedrock_model_id" {
  description = "Bedrock model ID or inference profile for document generation."
  type        = string
}

variable "enable_guardrail" {
  description = "Whether to create a Bedrock Guardrail."
  type        = bool
  default     = true
}

variable "task_role_name" {
  description = "Name of the ECS task IAM role to attach Bedrock invoke permissions to."
  type        = string
}

variable "documents_bucket_arn" {
  description = "ARN of the S3 bucket used to store templates and generated documents."
  type        = string
}

variable "tags" {
  description = "Common tags."
  type        = map(string)
  default     = {}
}
