output "kms_rds_key_arn" {
  description = "KMS key ARN for RDS/Aurora encryption."
  value       = aws_kms_key.rds.arn
}

output "kms_secrets_key_arn" {
  description = "KMS key ARN for Secrets Manager."
  value       = aws_kms_key.secrets.arn
}

output "kms_logs_key_arn" {
  description = "KMS key ARN for CloudWatch Logs."
  value       = aws_kms_key.logs.arn
}

output "kms_s3_key_arn" {
  description = "KMS key ARN for S3."
  value       = aws_kms_key.s3.arn
}

output "aurora_secret_arn" {
  description = "Secrets Manager ARN for Aurora master credentials."
  value       = aws_secretsmanager_secret.aurora.arn
}

output "aurora_password" {
  description = "Generated Aurora master password (sensitive)."
  value       = random_password.aurora.result
  sensitive   = true
}

output "google_oidc_secret_arn" {
  description = "Secrets Manager ARN for the Google OIDC client credentials."
  value       = aws_secretsmanager_secret.google_oidc.arn
}

output "waf_web_acl_arn" {
  description = "ARN of the regional WAF Web ACL for the ALB."
  value       = aws_wafv2_web_acl.alb.arn
}
