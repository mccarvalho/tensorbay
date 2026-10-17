# NeoCloud Platform — Release 1 Foundation (Terraform)

Infrastructure-as-Code for the **Release 1 / Commercial Control Plane (MVP)** foundation of the
NeoCloud GPU Control Platform, following the technology strategy in section 24 of the product plan
(`NeoCloud_GPU_Product_Plan_EN.md`).

> This repository provisions the **AWS foundation + runtime** for the modular-monolith FastAPI
> backend. It does **not** contain the application code. Nothing is deployed automatically — you
> review the plan and run `terraform apply` yourself.

## What this provisions

| Area | Resources |
|------|-----------|
| Networking | VPC (`/16`), 3 subnet tiers (public / private-app / private-data) across 2 AZs, Internet Gateway, NAT Gateway(s), route tables, VPC Flow Logs, security groups |
| Security | 4 KMS CMKs (RDS, Secrets, Logs, S3) with rotation, Secrets Manager (Aurora creds + Google OIDC), WAFv2 Web ACL (managed rules + rate limiting) |
| Data | Aurora PostgreSQL **Serverless v2** (encrypted), ElastiCache **Redis** (encrypted, Multi-AZ) |
| Compute | ECR repo, ECS **Fargate** cluster (Container Insights), Application Load Balancer, task definition + service for the FastAPI monolith |
| Identity | Cognito User Pool, **Google Workspace OIDC federation**, hosted UI domain, app client, 10 RBAC groups (section 20) |
| Messaging / Observability | EventBridge domain bus (+ archive), CloudWatch dashboard, alarms, SNS topic |
| Storage | S3 bucket for platform/metering data (versioned, KMS-encrypted, public access blocked) |

## Layout

```
infra/terraform/
├── versions.tf              # Terraform + provider pins, (commented) S3 backend
├── providers.tf             # AWS provider + default tags
├── variables.tf             # All root input variables
├── locals.tf                # Naming, AZ discovery, common tags
├── main.tf                  # Wires modules together + S3 data bucket
├── outputs.tf               # Key outputs (endpoints, Cognito, SSO redirect URI)
├── terraform.tfvars.example # Copy to terraform.tfvars and customize
└── modules/
    ├── networking/          # VPC, subnets, NAT, routes, security groups
    ├── security/            # KMS, Secrets Manager, WAF
    ├── data/                # Aurora PostgreSQL, ElastiCache Redis
    ├── compute/             # ECR, ECS Fargate, ALB, IAM
    ├── identity/            # Cognito + Google Workspace SSO + RBAC groups
    └── observability/       # EventBridge, CloudWatch, SNS
```

## Prerequisites

- Terraform `>= 1.5`
- AWS credentials with permissions to create the above (configure via `aws configure` or env vars)
- (For SSO) A Google Workspace organization and access to Google Cloud Console

## Deploy

```bash
cd infra/terraform

# 1. Prepare variables
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars

# 2. Initialize (local state for first run)
terraform init

# 3. Review the plan
terraform plan

# 4. Apply when satisfied
terraform apply
```

### (Recommended) Remote state

Before team use, create an S3 bucket + DynamoDB lock table, then uncomment the `backend "s3"`
block in `versions.tf` and run `terraform init -migrate-state`.

```bash
aws s3api create-bucket --bucket neocloud-tfstate-<ACCOUNT_ID> --region us-east-1
aws dynamodb create-table --table-name neocloud-tflock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST --region us-east-1
```

## Google Workspace SSO setup

The platform uses **Cognito as the application IdP**, with **Google Workspace federated as an
OIDC identity provider**. Login is delegated to Google; Cognito issues the JWTs the API validates,
preserving RBAC and tenant isolation.

Two-step chicken-and-egg: Cognito needs the Google client ID/secret, and Google needs the Cognito
redirect URI. Do this:

1. **First apply** with empty Google values (`google_oidc_client_id = ""`). This creates the Cognito
   hosted UI domain. Grab the redirect URI from the output:
   ```bash
   terraform output google_idp_redirect_uri
   # e.g. https://neocloud-dev-auth.auth.us-east-1.amazoncognito.com/oauth2/idpresponse
   ```
2. **In Google Cloud Console** (APIs & Services → Credentials):
   - Create an **OAuth client ID** of type **Web application**.
   - Under *Authorized redirect URIs*, add the URI from step 1.
   - On the OAuth consent screen, set **User type = Internal** so only your Workspace org can log in.
   - Copy the generated **Client ID** and **Client secret**.
3. **Second apply** with the Google values set in `terraform.tfvars`:
   ```hcl
   google_oidc_client_id     = "xxxx.apps.googleusercontent.com"
   google_oidc_client_secret = "GOCSPX-xxxx"
   ```
   ```bash
   terraform apply
   ```
   This creates the Google IdP in Cognito and adds it to the app client's supported providers.
4. Test the hosted UI:
   ```bash
   terraform output cognito_hosted_ui_url
   ```
   The login page will show a **Sign in with Google** button.

> The Google client secret is also stored in Secrets Manager at `neocloud/sso/google-oidc` so the
> backend can reference it without hardcoding.

## RBAC groups

Cognito groups are created for the 10 roles in section 20: `SUPER_ADMIN`, `EXECUTIVE`,
`SALES_MANAGER`, `SALES`, `FINANCE`, `OPERATIONS_MANAGER`, `OPERATIONS`, `CLOUD_ADMIN`,
`CUSTOMER_ADMIN`, `CUSTOMER_USER`. Assign users to groups; the group claim flows into the ID token
for the API to authorize against.

## Deploying the application image

1. Build and push your FastAPI image to the ECR repo:
   ```bash
   ECR_URL=$(terraform output -raw ecr_repository_url)
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin "$ECR_URL"
   docker build -t "$ECR_URL:latest" .
   docker push "$ECR_URL:latest"
   ```
2. Set `container_image = "<ECR_URL>:latest"` in `terraform.tfvars` and `terraform apply`,
   or update the ECS service to the new task definition.
3. Ensure the app exposes a `GET /health` endpoint returning `2xx` (the ALB target group health check).

## Cost note

This foundation creates billable resources even when idle: NAT Gateway(s), Aurora Serverless v2
(min ACUs), ElastiCache nodes, the ALB, and Fargate tasks. For a dev environment expect roughly
a few hundred USD/month depending on usage. Use `single_nat_gateway = true` and low ACU/desired
counts to minimize dev cost. Run `terraform destroy` to tear down when not in use.

## Production hardening (not included in this dev foundation)

- Add an **HTTPS (443) listener** on the ALB with an ACM certificate + a custom domain, and redirect HTTP→HTTPS.
- Set Aurora `deletion_protection = true` and `skip_final_snapshot = false`.
- Enable GuardDuty, Security Hub, and AWS Config (section 24 security stack).
- Use one NAT gateway per AZ (`single_nat_gateway = false`).
- Scope IAM task policies to least privilege per bounded context.
```

## CI/CD (GitHub Actions, keyless via OIDC)

Workflows live at the repo root in `.github/workflows/`:
- **ci.yml** — runs ruff + pytest on pushes/PRs touching `app/**`.
- **cd.yml** — on push to `main`: builds the Docker image, pushes to ECR, registers a new ECS task definition pointing at the new image, and rolls the service.

Authentication is **keyless** — GitHub Actions assumes an AWS role via OIDC (no stored access keys). Provision the provider + role with Terraform:

```hcl
# terraform.tfvars
enable_cicd                 = true
github_org                  = "your-org"
github_repo                 = "neocloud-platform"
github_create_oidc_provider = true   # false if the account already has it
```

```bash
terraform apply
terraform output cicd_deploy_role_arn
```

Then in the GitHub repo, add a **repository variable** `AWS_DEPLOY_ROLE_ARN` set to that output, and create an environment named `dev` (Settings → Environments). Pushes to `main` will now deploy automatically.

> The deploy role is least-privilege: it may only push to the `neocloud-dev-api`
> ECR repo, register task definitions, update the `neocloud-dev-api` service, and
> pass the ECS task/execution roles. The trust policy restricts assumption to the
> specified repo on the `main` branch.
