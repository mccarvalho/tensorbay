##############################################
# Email (SES) bounce & complaint handling
#
# Creates an SES v2 configuration set that publishes BOUNCE and COMPLAINT
# events to an SNS topic, which emails the operator. The application sends
# through this configuration set so every invite is tracked. SES account-level
# suppression (on by default) still auto-suppresses hard bounces/complaints;
# this module adds visibility + operator notification on top.
##############################################

# SNS topic that receives SES bounce/complaint events.
resource "aws_sns_topic" "ses_events" {
  name = "${var.name_prefix}-ses-events"
  tags = var.tags
}

# Email the operator on every published event.
resource "aws_sns_topic_subscription" "ses_events_email" {
  count     = var.notification_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.ses_events.arn
  protocol  = "email"
  endpoint  = var.notification_email
}

# Allow SES to publish to the topic.
resource "aws_sns_topic_policy" "ses_publish" {
  arn = aws_sns_topic.ses_events.arn
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowSESPublish"
      Effect    = "Allow"
      Principal = { Service = "ses.amazonaws.com" }
      Action    = "sns:Publish"
      Resource  = aws_sns_topic.ses_events.arn
      Condition = {
        StringEquals = { "AWS:SourceAccount" = var.account_id }
      }
    }]
  })
}

# SES v2 configuration set the app sends through.
resource "aws_sesv2_configuration_set" "main" {
  configuration_set_name = "${var.name_prefix}-cfgset"

  reputation_options {
    reputation_metrics_enabled = true
  }

  sending_options {
    sending_enabled = true
  }
}

# Route bounce + complaint (and rejects/delivery failures) events to SNS.
resource "aws_sesv2_configuration_set_event_destination" "sns" {
  configuration_set_name = aws_sesv2_configuration_set.main.configuration_set_name
  event_destination_name = "${var.name_prefix}-bounce-complaint"

  event_destination {
    enabled              = true
    matching_event_types = ["BOUNCE", "COMPLAINT", "REJECT", "DELIVERY_DELAY"]

    sns_destination {
      topic_arn = aws_sns_topic.ses_events.arn
    }
  }
}
