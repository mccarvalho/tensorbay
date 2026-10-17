# CloudFront distribution fronting the private S3 bucket via Origin Access Control.

resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "${var.name_prefix}-web-oac"
  description                       = "OAC for ${var.name_prefix} web"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  default_root_object = "index.html"
  comment             = "${var.name_prefix} NeoCloud web"
  price_class         = "PriceClass_100" # NA + EU edge locations
  tags                = var.tags

  origin {
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_id                = "s3-${aws_s3_bucket.site.id}"
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  # API origin: the application ALB (HTTP-only). CloudFront terminates TLS with
  # the viewer and talks HTTP to the ALB inside AWS, so the browser only ever
  # makes same-origin HTTPS calls (no mixed-content, no CORS).
  origin {
    domain_name = var.api_origin_domain
    origin_id   = "alb-api"
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "s3-${aws_s3_bucket.site.id}"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    # AWS managed CachingOptimized policy.
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"

    # SPA client-route rewrite (request-side). Replaces the old 403/404 custom
    # error responses so API errors are never converted to the SPA shell.
    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_router.arn
    }
  }

  # API behaviors -> ALB. No caching; forward everything (incl. Authorization).
  # AllViewer origin request policy + CachingDisabled cache policy (AWS managed).
  dynamic "ordered_cache_behavior" {
    for_each = toset(["/v1/*", "/health", "/docs", "/openapi.json", "/redoc"])
    content {
      path_pattern             = ordered_cache_behavior.value
      target_origin_id         = "alb-api"
      viewer_protocol_policy   = "redirect-to-https"
      allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
      cached_methods           = ["GET", "HEAD"]
      compress                 = true
      cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" # Managed-CachingDisabled
      origin_request_policy_id = "216adef6-5c7f-47e4-b989-5492eafa07d3" # Managed-AllViewer
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
