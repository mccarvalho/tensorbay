########################################
# Pre sign-up trigger: link Google sign-ins to the invited user
#
# Without this, signing in with Google creates a second, role-less Cognito user
# next to the invited one (duplicate user + 403s). See
# lambda/pre_signup/handler.py for the logic and safety rules.
########################################

data "archive_file" "pre_signup" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/pre_signup"
  output_path = "${path.module}/.build/pre_signup.zip"
  excludes    = ["__pycache__", "*.pyc"]
}

resource "aws_cloudwatch_log_group" "pre_signup" {
  name              = "/aws/lambda/${var.name_prefix}-cognito-pre-signup"
  retention_in_days = 30
  tags              = var.tags
}

data "aws_iam_policy_document" "pre_signup_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "pre_signup" {
  name               = "${var.name_prefix}-cognito-pre-signup"
  assume_role_policy = data.aws_iam_policy_document.pre_signup_assume.json
  tags               = var.tags
}

# Least privilege: logging to its own group, and only the two Cognito calls it
# needs, only on this user pool.
resource "aws_iam_role_policy" "pre_signup" {
  name = "${var.name_prefix}-cognito-pre-signup"
  role = aws_iam_role.pre_signup.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.pre_signup.arn}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["cognito-idp:ListUsers", "cognito-idp:AdminLinkProviderForUser"]
        Resource = aws_cognito_user_pool.this.arn
      },
    ]
  })
}

resource "aws_lambda_function" "pre_signup" {
  function_name    = "${var.name_prefix}-cognito-pre-signup"
  role             = aws_iam_role.pre_signup.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.pre_signup.output_path
  source_code_hash = data.archive_file.pre_signup.output_base64sha256
  timeout          = 10
  memory_size      = 128
  tags             = var.tags

  depends_on = [aws_cloudwatch_log_group.pre_signup]
}

resource "aws_lambda_permission" "pre_signup_cognito" {
  statement_id  = "AllowCognitoInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pre_signup.function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = aws_cognito_user_pool.this.arn
}
