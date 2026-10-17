########################################
# AI document generation (Amazon Bedrock)
# Generates MSAs, LOIs, Proposals, and Contracts from structured deal data
# + templates. Invoked by the FastAPI backend via the ECS task role.
########################################

########################################
# Bedrock Guardrail (recommended for legal content)
########################################

resource "aws_bedrock_guardrail" "docs" {
  count = var.enable_guardrail ? 1 : 0

  name                      = "${var.name_prefix}-docgen-guardrail"
  description               = "Guardrail for AI-generated legal/commercial documents"
  blocked_input_messaging   = "This request cannot be processed."
  blocked_outputs_messaging = "The generated content was blocked by content policy."

  content_policy_config {
    filters_config {
      input_strength  = "HIGH"
      output_strength = "HIGH"
      type            = "HATE"
    }
    filters_config {
      input_strength  = "HIGH"
      output_strength = "HIGH"
      type            = "INSULTS"
    }
    filters_config {
      input_strength  = "HIGH"
      output_strength = "HIGH"
      type            = "SEXUAL"
    }
    filters_config {
      input_strength  = "HIGH"
      output_strength = "HIGH"
      type            = "VIOLENCE"
    }
    filters_config {
      input_strength  = "HIGH"
      output_strength = "HIGH"
      type            = "MISCONDUCT"
    }
    filters_config {
      input_strength  = "NONE"
      output_strength = "NONE"
      type            = "PROMPT_ATTACK"
    }
  }

  # Prevent leaking sensitive PII into generated documents unintentionally.
  sensitive_information_policy_config {
    pii_entities_config {
      action = "ANONYMIZE"
      type   = "CREDIT_DEBIT_CARD_NUMBER"
    }
    pii_entities_config {
      action = "ANONYMIZE"
      type   = "US_SOCIAL_SECURITY_NUMBER"
    }
  }

  tags = var.tags
}

########################################
# IAM: allow the ECS task role to invoke Bedrock models/inference profiles
# and read/write document templates and outputs in S3.
########################################

resource "aws_iam_role_policy" "bedrock_invoke" {
  name = "${var.name_prefix}-bedrock-invoke"
  role = var.task_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokeBedrockModels"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        # Cross-region inference profiles invoke the foundation models in any
        # of the region's partners, so allow the FM ARNs broadly plus the
        # inference profile ARNs. Scope to Anthropic models.
        Resource = [
          "arn:aws:bedrock:*::foundation-model/anthropic.*",
          "arn:aws:bedrock:${var.aws_region}:${var.account_id}:inference-profile/*",
          "arn:aws:bedrock:*:${var.account_id}:inference-profile/*"
        ]
      },
      {
        Sid    = "ApplyGuardrail"
        Effect = "Allow"
        Action = ["bedrock:ApplyGuardrail"]
        Resource = var.enable_guardrail ? [
          aws_bedrock_guardrail.docs[0].guardrail_arn
        ] : ["arn:aws:bedrock:${var.aws_region}:${var.account_id}:guardrail/*"]
      },
      {
        Sid    = "DocumentStorageAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.documents_bucket_arn,
          "${var.documents_bucket_arn}/documents/*",
          "${var.documents_bucket_arn}/templates/*"
        ]
      }
    ]
  })
}
