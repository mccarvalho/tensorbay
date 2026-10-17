# NeoCloud Platform — Application (FastAPI Modular Monolith)

Release 1 (Commercial & Capacity Control Plane / MVP) backend for the NeoCloud
GPU Control Platform. Implements the bounded contexts as a modular monolith per
section 24 of the product plan.

## Domains (bounded contexts)

| Module | Plan EPIC | Routes |
|--------|-----------|--------|
| `domains/customers` | 01 Customer Management | `/v1/customers` (+ contacts, billing accounts) |
| `domains/catalog` | 02 Product Catalog & Pricing | `/v1/catalog/skus`, `/price-books`, `/prices` |
| `domains/sales` | 03 Sales & Opportunity | `/v1/sales/opportunities`, `/quotes` |
| `domains/contracts` | 04 Contract Management | `/v1/contracts` (+ items, commitments, price agreements) |
| `domains/inventory` | 05 GPU Asset Inventory | `/v1/inventory/regions…/gpus` |
| `domains/capacity` | 06 Capacity Management | `/v1/capacity/ledger`, `/capacity/check` |
| `domains/reservations` | 07 Reservation & Allocation | `/v1/reservations` (+ allocations) |
| `domains/documents` | AI doc generation | `/v1/documents/generate` (MSA/LOI/Proposal/Contract) |

Cross-cutting: `auth` (Cognito JWT + RBAC), `audit` (audit trail), `core`
(config, structured logging, correlation-ID middleware), `db` (async SQLAlchemy).

## Key design points

- **Reservation (commercial) and Allocation (physical) are separate entities** — hardware can be swapped without touching the contract.
- **Operational status and commercial status on GPU assets are independent fields.**
- **Capacity ledger** computes physical/operational/reserved/allocated/available from inventory and powers the **overselling check**.
- **AI documents default to a DRAFT/GENERATED status** — legal docs require human review/approval (`/documents/{id}/approve`).
- Every write records an **audit entry** (who/when/action/entity/old/new/correlation-id).

## Run locally

```bash
cd app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Local mode: SQLite + auth disabled (stub SUPER_ADMIN user)
export DATABASE_URL="sqlite+aiosqlite:///./local.db"
export AUTH_ENABLED=false
alembic upgrade head
uvicorn neocloud.main:app --reload --port 8000
# http://localhost:8000/docs
```

## Tests

```bash
source .venv/bin/activate
pytest -q
```

## Database migrations (Alembic, async)

```bash
# Autogenerate after model changes
alembic revision --autogenerate -m "describe change"
# Apply
alembic upgrade head
```

In production the DB URL is resolved from Secrets Manager via `AURORA_SECRET_ARN`
+ `AURORA_HOST` (injected by the ECS task definition).

## Build & deploy to ECR / ECS (us-east-2)

The infrastructure (ECS Fargate cluster `neocloud-dev-cluster`, service
`neocloud-dev-api`, ECR repo) is provisioned by `../infra/terraform`.

```bash
ECR_URL=369607683065.dkr.ecr.us-east-2.amazonaws.com/neocloud-dev-api
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin "$ECR_URL"
docker build -t "$ECR_URL:latest" .
docker push "$ECR_URL:latest"

# Point the service at the image and roll:
#   set container_image = "<ECR_URL>:latest" in terraform.tfvars and apply,
#   or: aws ecs update-service --cluster neocloud-dev-cluster --service neocloud-dev-api --force-new-deployment --region us-east-2
```

The container listens on `:8000` and serves `GET /health` for the ALB target
group health check.

## Environment variables (injected by ECS)

`APP_ENV`, `AWS_REGION`, `BEDROCK_MODEL_ID`, `DOCUMENTS_BUCKET`,
`AURORA_SECRET_ARN`, `GOOGLE_SSO_SECRET_ARN`, `COGNITO_USER_POOL_ID`,
`COGNITO_CLIENT_ID`. Set `AURORA_HOST` to the Aurora writer endpoint.
