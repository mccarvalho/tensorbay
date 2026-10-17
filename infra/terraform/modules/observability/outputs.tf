output "event_bus_name" {
  description = "Name of the domain EventBridge bus."
  value       = aws_cloudwatch_event_bus.domain.name
}

output "event_bus_arn" {
  description = "ARN of the domain EventBridge bus."
  value       = aws_cloudwatch_event_bus.domain.arn
}

output "alarm_topic_arn" {
  description = "SNS topic ARN for CloudWatch alarms."
  value       = aws_sns_topic.alarms.arn
}

output "dashboard_name" {
  description = "CloudWatch dashboard name."
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}
