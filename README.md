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
├── web/                      # React + Vite + TS frontend (TensorBay brand)
│   ├── public/brand/         # official TensorBay logo + symbol
│   └── src/                  # auth (PKCE SSO), api client, pages, components
├── infra/terraform/          # AWS infrastructure as code
│   └── modules/              # networking, security, data, compute,
│                             #   identity, observability, ai, cicd, frontend
├── .github/workflows/        # ci.yml (lint+test), cd.yml (API), cd-web.yml (web)
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
| `cd-web.yml` | push to `main` touching `web/**` | npm build → sync to S3 → invalidate CloudFront |

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

Release 1 (Commercial & Capacity Control Plane) — **live** in `us-east-2`:

- **Frontend:** https://d22xy9yyfwju3n.cloudfront.net (React SPA, TensorBay brand, S3+CloudFront)
- **API:** http://neocloud-dev-alb-1924778288.us-east-2.elb.amazonaws.com (ECS Fargate)
- Database migrated (27 tables); full authenticated CRUD validated end-to-end.
- Cognito + Google Workspace SSO handshake validated.

See [`STATUS.md`](STATUS.md) for the current state and the short list of manual
actions remaining.

### Remaining operational steps (manual, account-owner)
- **Enable the Anthropic model**: Bedrock console (us-east-2) → Model access →
  submit the Anthropic *use case details* form. This is the only thing blocking
  AI document generation (the app is otherwise fully wired).
- **Rotate the Google client secret** and confirm the consent screen is **Internal**.
- Optional hardening: HTTPS + custom domain on the ALB (frontend is already HTTPS).
