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

variable "aliases" {
  description = "Alternate domain names (CNAMEs) served by the distribution."
  type        = list(string)
  default     = []
}

variable "acm_certificate_arn" {
  description = "Validated us-east-1 ACM certificate covering `aliases`. Empty = default CloudFront certificate."
  type        = string
  default     = ""
}
