# ============================================================================
# DEV environment (AWS account 369607683065, us-east-2)
# Mirrors the live dev deployment. Non-sensitive — safe to commit.
# The Google OAuth CLIENT SECRET is NOT here; pass it at apply time via
# -var or a gitignored secrets file (see envs/README or backend notes).
# Usage:
#   terraform init -reconfigure -backend-config=backend-dev.hcl
#   terraform plan  -var-file=envs/dev.tfvars
# ============================================================================

environment = "dev"
aws_region  = "us-east-2"

# Networking — single NAT is fine for dev
single_nat_gateway = true

# Data layer — dev baseline (low floor)
aurora_min_capacity      = 0.5
aurora_max_capacity      = 4
redis_num_cache_clusters = 2

# Compute
service_desired_count = 2

# Observability
log_retention_days = 30

# Email (SES) — invite sending. mcarvalho@tensorbay.io is SES-verified in dev
# (single-address, no DNS). Switch to no-reply@tensorbay.io once the domain is
# DKIM-verified. Empty would fall back to Cognito's native invite + temp password.
ses_from_email = "mcarvalho@tensorbay.io"
app_base_url   = "https://d22xy9yyfwju3n.cloudfront.net"

# CI/CD — GitHub Actions keyless deploy role (auto-deploy on push to main)
enable_cicd                 = true
github_org                  = "mccarvalho"
github_repo                 = "tensorbay"
github_create_oidc_provider = true
github_sub_patterns = [
  "repo:mccarvalho/tensorbay:*",     # classic format
  "repo:mccarvalho@*/tensorbay@*:*", # immutable-ID format
]

# Pin the application image to the dev ECR repo (CD overrides per-commit).
container_image = "369607683065.dkr.ecr.us-east-2.amazonaws.com/neocloud-dev-api:latest"

# Identity (Cognito + Google Workspace SSO)
cognito_domain_prefix = "neocloud-dev-auth"
cognito_callback_urls = [
  "https://d22xy9yyfwju3n.cloudfront.net/callback",
  "http://localhost:3000/callback",
  "https://localhost:3000/callback",
]
cognito_logout_urls = [
  "https://d22xy9yyfwju3n.cloudfront.net/",
  "http://localhost:3000/",
  "https://localhost:3000/logout",
]

# Google Workspace SSO — shared OAuth client across dev/prod.
# Client ID is not secret; the client SECRET is passed separately at apply time.
google_oidc_client_id = "185060429707-e0aidmvu1hnsil8u5elb39j9e0053o9r.apps.googleusercontent.com"
ses_notification_email = "mcarvalho@tensorbay.io"

economics_alert_emails = "mcarvalho@tensorbay.io"
