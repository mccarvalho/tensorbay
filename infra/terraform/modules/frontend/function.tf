# CloudFront Function (viewer-request) for SPA routing.
# Rewrites client-side routes (paths without a file extension, excluding API
# paths) to /index.html, so react-router can handle them. This REPLACES the
# distribution-wide custom_error_response (403/404 -> index.html), which had the
# side effect of converting the API's legitimate 403/404 JSON responses into the
# SPA HTML shell.

resource "aws_cloudfront_function" "spa_router" {
  name    = "${var.name_prefix}-spa-router"
  runtime = "cloudfront-js-2.0"
  comment = "SPA client-route rewrite to /index.html (excludes API paths)"
  publish = true
  code    = <<-EOT
    function handler(event) {
      var request = event.request;
      var uri = request.uri;

      // Never rewrite API / system paths — let them hit the ALB origin as-is.
      if (
        uri.startsWith('/v1/') ||
        uri === '/health' ||
        uri === '/docs' ||
        uri === '/redoc' ||
        uri === '/openapi.json'
      ) {
        return request;
      }

      // Static assets (have a file extension) pass through to S3 unchanged.
      var lastSegment = uri.substring(uri.lastIndexOf('/') + 1);
      if (lastSegment.indexOf('.') !== -1) {
        return request;
      }

      // Everything else is a client-side route -> serve the SPA shell.
      request.uri = '/index.html';
      return request;
    }
  EOT
}
