output "guardrail_id" {
  description = "Bedrock Guardrail ID (empty if disabled)."
  value       = var.enable_guardrail ? aws_bedrock_guardrail.docs[0].guardrail_id : ""
}

output "guardrail_arn" {
  description = "Bedrock Guardrail ARN (empty if disabled)."
  value       = var.enable_guardrail ? aws_bedrock_guardrail.docs[0].guardrail_arn : ""
}

output "guardrail_version" {
  description = "Bedrock Guardrail version (empty if disabled)."
  value       = var.enable_guardrail ? aws_bedrock_guardrail.docs[0].version : ""
}

output "bedrock_model_id" {
  description = "Bedrock model/inference profile ID used for document generation."
  value       = var.bedrock_model_id
}
