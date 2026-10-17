output "deploy_role_arn" {
  description = "IAM role ARN for GitHub Actions to assume via OIDC. Set as AWS_DEPLOY_ROLE_ARN secret/variable in GitHub."
  value       = aws_iam_role.deploy.arn
}

output "oidc_provider_arn" {
  description = "GitHub OIDC provider ARN."
  value       = local.oidc_provider_arn
}
