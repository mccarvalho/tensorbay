# ============================================================================
# PROD environment (AWS account 104005344884, us-east-2)
# Non-sensitive — safe to commit. The Google OAuth CLIENT SECRET is NOT here;
# pass it at apply time via -var or a gitignored secrets file.
# Usage (PROD creds in the environment):
#   terraform init -reconfigure -backend-config=backend-prod.hcl
#   terraform plan  -var-file=envs/prod.tfvars
# ============================================================================

environment = "prod"
aws_region  = "us-east-2"

# Networking — one NAT gateway per AZ for HA egress
single_nat_gateway = false

# Data layer — prod baseline (higher floor + headroom; NOT scaled to zero)
aurora_min_capacity      = 1
aurora_max_capacity      = 8
redis_num_cache_clusters = 2

# Compute
service_desired_count = 2

# Observability — longer retention for prod audit
log_retention_days = 90

# Email (SES) — not yet configured in prod; empty falls back to Cognito's native
# invite. Set to no-reply@tensorbay.io once SES is verified in the prod account.
ses_from_email = ""
app_base_url   = "https://d268drxlb2qrjo.cloudfront.net"

# CI/CD — prod needs its own GitHub OIDC provider + deploy role in this account.
# The PROD deploy is TAG/MANUAL-gated at the workflow level (see .github/workflows);
# the subject patterns below allow the release workflow to assume the role.
enable_cicd                 = true
github_org                  = "mccarvalho"
github_repo                 = "tensorbay"
github_create_oidc_provider = true
# Allow tag pushes (v*) and the prod GitHub Environment to assume the deploy role.
github_sub_patterns = [
  "repo:mccarvalho/tensorbay:ref:refs/tags/v*",
  "repo:mccarvalho@*/tensorbay@*:ref:refs/tags/v*",
  "repo:mccarvalho/tensorbay:environment:prod",
  "repo:mccarvalho@*/tensorbay@*:environment:prod",
]

# Pin the application image to the PROD ECR repo (CD overrides per-release).
# The real image has been pushed to prod ECR, so the pin is now active.
container_image = "104005344884.dkr.ecr.us-east-2.amazonaws.com/neocloud-prod-api:latest"

# Identity (Cognito + Google Workspace SSO)
# cognito_domain_prefix must be globally unique within the region.
cognito_domain_prefix = "neocloud-prod-auth"
# Prod CloudFront URL wired in after first apply (SSO second pass).
cognito_callback_urls = [
  "https://d268drxlb2qrjo.cloudfront.net/callback",
  "http://localhost:3000/callback",
  "https://localhost:3000/callback",
]
cognito_logout_urls = [
  "https://d268drxlb2qrjo.cloudfront.net/",
  "http://localhost:3000/",
  "https://localhost:3000/logout",
]

# Google Workspace SSO — SAME OAuth client as dev (shared). Client ID is not
# secret; the client SECRET is passed separately at apply time.
google_oidc_client_id = "185060429707-e0aidmvu1hnsil8u5elb39j9e0053o9r.apps.googleusercontent.com"
