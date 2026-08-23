# NeoCloud GPU Control Platform

Commercial & Infrastructure Control Plane for GPU NeoCloud.

## Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Make

### Development Setup

```bash
# Start all services (app + PostgreSQL + Redis)
make dev

# Or run manually:
cp .env.example .env
docker compose up -d db redis
pip install -e ".[dev]"
alembic upgrade head
uvicorn neocloud.main:app --reload
```

The API is available at `http://localhost:8000`.
OpenAPI docs at `http://localhost:8000/docs`.

### Commands

```bash
make dev              # Start with docker-compose (hot reload)
make test             # Run tests with coverage
make lint             # Run ruff + mypy
make format           # Auto-format code
make migrate          # Run pending migrations
make migrate-create msg="description"  # Create new migration
make build            # Build Docker image
make clean            # Stop containers, remove volumes
```

## Architecture

**Modular monolith** with bounded contexts:

```
src/neocloud/
├── main.py              # FastAPI app
├── common/              # Shared infrastructure (DB, auth, events, errors)
├── customers/           # Customer management
├── catalog/             # SKUs & pricing
├── sales/               # Opportunities, quotes, capacity checks
├── contracts/           # Contracts, commitments, SLA
├── inventory/           # Regions, DCs, clusters, racks, servers, GPUs
├── capacity/            # Capacity ledger, availability, incoming
├── reservations/        # Reservation lifecycle
├── allocations/         # Physical resource binding
├── iam/                 # Users, roles, permissions
├── audit/               # Audit trail
└── dashboards/          # Read-only aggregation views
```

Each domain module follows the pattern:
- `models.py` — SQLAlchemy models
- `schemas.py` — Pydantic request/response schemas
- `router.py` — FastAPI route handlers
- `service.py` — Business logic
- `repository.py` — Data access layer
- `events.py` — Domain events

## API

All endpoints are versioned under `/v1/`:

| Prefix | Domain |
|--------|--------|
| `/v1/customers` | Customer management |
| `/v1/catalog` | SKUs & pricing |
| `/v1/sales` | Opportunities & quotes |
| `/v1/contracts` | Contract management |
| `/v1/inventory` | Infrastructure inventory |
| `/v1/capacity` | Capacity management |
| `/v1/reservations` | Reservations |
| `/v1/allocations` | Allocations |
| `/v1/iam` | Identity & access |
| `/v1/audit` | Audit logs |

## Tech Stack

- **Runtime:** Python 3.11, FastAPI, Uvicorn
- **Database:** PostgreSQL 16 (Aurora in production)
- **Cache:** Redis 7
- **ORM:** SQLAlchemy 2.0 (async)
- **Migrations:** Alembic
- **Events:** AWS EventBridge
- **Auth:** AWS Cognito + JWT
- **IaC:** Terraform (in `/infra`)
