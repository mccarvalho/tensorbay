# Custom domain for the CloudFront distribution (e.g. crm.tensorbay.io).
#
# CloudFront only accepts ACM certificates from us-east-1, hence the aliased
# provider. DNS lives in Cloudflare (not Route 53), so validation is manual:
# apply once with attach = false to create the certificate, add the CNAME(s) from
# `validation_records` in Cloudflare (DNS only, not proxied), wait for ISSUED, then
# apply again with attach = true to wait for validation and expose the ARN.

terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      configuration_aliases = [aws.us_east_1]
    }
  }
}

variable "domain_name" {
  description = "Custom domain, e.g. crm.tensorbay.io. Empty disables the module."
  type        = string
  default     = ""
}

variable "attach" {
  description = "Wait for the certificate to validate and expose its ARN for CloudFront."
  type        = bool
  default     = false
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  enabled = var.domain_name != ""
}

resource "aws_acm_certificate" "this" {
  count    = local.enabled ? 1 : 0
  provider = aws.us_east_1

  domain_name       = var.domain_name
  validation_method = "DNS"
  tags              = var.tags

  lifecycle {
    create_before_destroy = true
  }
}

# Blocks until ACM sees the validation CNAME (default timeout 75 min).
resource "aws_acm_certificate_validation" "this" {
  count    = local.enabled && var.attach ? 1 : 0
  provider = aws.us_east_1

  certificate_arn = aws_acm_certificate.this[0].arn
}

output "validation_records" {
  description = "DNS records to create in Cloudflare (DNS only) to validate the certificate."
  value = local.enabled ? [
    for o in aws_acm_certificate.this[0].domain_validation_options : {
      name  = o.resource_record_name
      type  = o.resource_record_type
      value = o.resource_record_value
    }
  ] : []
}

output "certificate_arn" {
  description = "Validated certificate ARN, or empty until attach = true."
  value       = local.enabled && var.attach ? aws_acm_certificate_validation.this[0].certificate_arn : ""
}

output "certificate_status" {
  value = local.enabled ? aws_acm_certificate.this[0].status : "DISABLED"
}
