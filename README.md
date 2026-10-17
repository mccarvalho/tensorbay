# NeoCloud GPU Control Platform

Proprietary platform to manage the commercial, operational, and financial
lifecycle of GPU infrastructure — evolving from a **Commercial & Capacity
Control Plane** (Release 1 / MVP) toward a full NeoCloud.

Lifecycle managed:
**Customer → Opportunity → Quote → Contract → Capacity → Reservation →
Allocation → Provisioning → Usage → Billing → Revenue/Margin**

See `NeoCloud_GPU_Product_Plan_EN.md` for the full product plan.

## Repository structure

```
.
├── app/                      # FastAPI modular monolith (Python 3.12)
│   ├── neocloud/             # Application package (bounded contexts)
│   │   ├── core/             # config, logging, correlation-id middleware
│   │   ├── auth/             # Cognito JWT validation + RBAC (10 roles)
│   │   ├── audit/            # audit trail service
│   │   ├── db/               # async SQLAlchemy base + session
│   │   └── domains/          # customers, catalog, inventory, capacity,
│   │                         #   sales, contracts, reservations, documents,
│   │                         #   dashboards
│   ├── migrations/           # Alembic (async)
│   ├── tests/                # pytest suite
│   └── Dockerfile
├── infra/terraform/          # AWS infrastructure as code
│   └── modules/              # networking, security, data, compute,
│                             #   identity, observability, ai, cicd
├── .github/workflows/        # ci.yml (lint+test), cd.yml (build+deploy)
└── NeoCloud_GPU_Product_Plan_EN.md
```

## Architecture (Release 1, AWS `us-east-2`)

- **Compute:** ECS Fargate behind an ALB (+ WAF), image in ECR
- **Data:** Aurora PostgreSQL Serverless v2, ElastiCache Redis (both encrypted)
- **Identity:** Amazon Cognito with **Google Workspace OIDC federation** (SSO)
- **AI:** Amazon Bedrock (Claude) for MSA/LOI/Proposal/Contract generation, with Guardrail
- **Security:** KMS CMKs, Secrets Manager (all secrets), WAF; VPC with public/app/data subnet tiers
- **Events/Obs:** EventBridge domain bus, CloudWatch dashboards/alarms
- **Account:** `369607683065`

## Getting started

- **Application:** see [`app/README.md`](app/README.md) — run locally, test, migrate, build image.
- **Infrastructure:** see [`infra/terraform/README.md`](infra/terraform/README.md) — provision, Google SSO setup, cost notes, prod hardening.

## CI/CD (GitHub Actions, keyless via OIDC)

Two workflows in `.github/workflows/`:

| Workflow | Trigger | Does |
|----------|---------|------|
| `ci.yml` | push/PR touching `app/**` | ruff lint + pytest |
| `cd.yml` | push to `main` touching `app/**` | build image → push ECR → register task def → update ECS service → wait stable |

**Authentication is keyless** — Actions assumes AWS IAM role
`arn:aws:iam::369607683065:role/neocloud-dev-gha-deploy` via GitHub OIDC
(no stored AWS keys). Trust is restricted to `mccarvalho/tensorbay` on `main`.

### Configuration (already set up)

- Repo **variable** `AWS_DEPLOY_ROLE_ARN` = the deploy role ARN above
- GitHub **environment** `dev`
- The OIDC provider + deploy role are provisioned by the `cicd` Terraform module
  (`enable_cicd = true` in `infra/terraform/terraform.tfvars`)

### Deploy flow

```
git push origin main        # changes under app/**
   → CI runs tests
   → CD builds & pushes image to ECR, rolls the ECS service
```

To deploy manually instead, see the commands in `app/README.md`.

## Status

Release 1 (Commercial & Capacity Control Plane) — infrastructure deployed to
`us-east-2`; application domains, AI document generation, and executive
dashboards implemented with a passing test suite. Not yet live-serving the app
image (placeholder until the first CD run).

### Remaining operational steps
- Enable Bedrock Claude **model access** in the Bedrock console (us-east-2).
- Complete **Google Workspace SSO** (second Terraform apply with Google client creds).
- First **CD deploy** replaces the placeholder container with the FastAPI image.
