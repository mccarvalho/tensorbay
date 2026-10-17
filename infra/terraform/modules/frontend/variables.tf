variable "name_prefix" {
  description = "Prefix for resource names (e.g., neocloud-dev)."
  type        = string
}

variable "tags" {
  description = "Common tags."
  type        = map(string)
  default     = {}
}

variable "api_origin_domain" {
  description = "ALB DNS name to use as the CloudFront API origin (e.g. neocloud-dev-alb-...elb.amazonaws.com)."
  type        = string
}
