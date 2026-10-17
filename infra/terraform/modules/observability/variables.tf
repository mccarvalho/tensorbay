variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "aws_region" {
  description = "AWS region for dashboard widgets."
  type        = string
}

variable "ecs_cluster_name" {
  description = "ECS cluster name for alarms/dashboard."
  type        = string
}

variable "ecs_service_name" {
  description = "ECS service name for alarms/dashboard."
  type        = string
}

variable "alb_arn_suffix" {
  description = "ALB ARN suffix (for CloudWatch dimensions)."
  type        = string
}

variable "alarm_email" {
  description = "Email to subscribe to the alarm SNS topic (optional)."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Common tags."
  type        = map(string)
  default     = {}
}
