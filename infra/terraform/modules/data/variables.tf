variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "data_subnet_ids" {
  description = "Private data subnet IDs for DB and cache subnet groups."
  type        = list(string)
}

variable "aurora_security_group_id" {
  description = "Security group ID for the Aurora cluster."
  type        = string
}

variable "redis_security_group_id" {
  description = "Security group ID for the Redis replication group."
  type        = string
}

variable "kms_rds_key_arn" {
  description = "KMS key ARN for Aurora storage encryption."
  type        = string
}

variable "aurora_engine_version" {
  description = "Aurora PostgreSQL engine version."
  type        = string
}

variable "aurora_database_name" {
  description = "Initial database name."
  type        = string
}

variable "aurora_master_username" {
  description = "Aurora master username."
  type        = string
}

variable "aurora_master_password" {
  description = "Aurora master password (from Secrets Manager / security module)."
  type        = string
  sensitive   = true
}

variable "aurora_min_capacity" {
  description = "Serverless v2 minimum ACU."
  type        = number
}

variable "aurora_max_capacity" {
  description = "Serverless v2 maximum ACU."
  type        = number
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type."
  type        = string
}

variable "redis_num_cache_clusters" {
  description = "Number of Redis nodes."
  type        = number
}

variable "tags" {
  description = "Common tags."
  type        = map(string)
  default     = {}
}
