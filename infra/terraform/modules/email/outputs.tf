output "configuration_set_name" {
  description = "SES configuration set name the app should send through."
  value       = aws_sesv2_configuration_set.main.configuration_set_name
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic receiving SES bounce/complaint events."
  value       = aws_sns_topic.ses_events.arn
}
