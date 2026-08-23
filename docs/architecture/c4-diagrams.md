# NeoCloud GPU Control Platform — C4 Architecture Diagrams

## Level 1: System Context

```mermaid
C4Context
    title NeoCloud GPU Control Platform - System Context

    Person(executive, "Executive", "CEO/CFO - views revenue, margin, utilization")
    Person(sales, "Sales Team", "Manages opportunities, quotes, contracts")
    Person(operations, "Operations", "Manages GPU infrastructure, provisioning")
    Person(finance, "Finance/FinOps", "Billing, commitments, margin analysis")
    Person(customer_admin, "Customer Admin", "Manages resources, users, billing")

    System(neocloud, "NeoCloud GPU Control Platform", "Manages commercial & operational lifecycle of GPU infrastructure")

    System_Ext(crm, "CRM System", "Salesforce/HubSpot - lead source")
    System_Ext(erp, "ERP/Accounting", "Invoice delivery, revenue recognition")
    System_Ext(gpu_infra, "GPU Infrastructure", "Kubernetes, Slurm, Bare Metal clusters")
    System_Ext(identity, "Identity Provider", "Cognito + Enterprise SSO/SAML")
    System_Ext(payment, "Payment Processor", "Stripe/wire transfer processing")
    System_Ext(monitoring, "Infrastructure Monitoring", "Prometheus, DCIM, power management")

    Rel(executive, neocloud, "Views dashboards, KPIs")
    Rel(sales, neocloud, "Manages pipeline, quotes, contracts")
    Rel(operations, neocloud, "Manages inventory, allocations, provisioning")
    Rel(finance, neocloud, "Manages billing, credits, reconciliation")
    Rel(customer_admin, neocloud, "Views resources, usage, invoices")

    Rel(neocloud, crm, "Syncs customers, opportunities")
    Rel(neocloud, erp, "Sends invoices, receives payments")
    Rel(neocloud, gpu_infra, "Provisions/deprovisions resources")
    Rel(neocloud, identity, "Authenticates users, federation")
    Rel(neocloud, payment, "Processes payments")
    Rel(monitoring, neocloud, "Sends health/telemetry data")
```

---

## Level 2: Container Diagram

```mermaid
C4Container
    title NeoCloud GPU Control Platform - Container Diagram

    Person(user, "Platform User", "Internal or Customer")

    System_Boundary(neocloud, "NeoCloud Platform") {
        Container(web_app, "Web Application", "React/Next.js", "Admin portal, dashboards, customer portal")
        Container(api_gateway, "API Gateway", "AWS ALB + WAF", "Rate limiting, auth routing, TLS termination")
        Container(backend, "Backend API", "Python/FastAPI", "Modular monolith - all business logic")
        Container(worker, "Background Workers", "Python/Celery", "Async jobs: capacity recalc, notifications")
        ContainerDb(db, "Primary Database", "PostgreSQL/Aurora", "All transactional data")
        ContainerDb(cache, "Cache", "Redis/ElastiCache", "Session, capacity snapshots, rate limits")
        Container(event_bus, "Event Bus", "AWS EventBridge", "Domain events between bounded contexts")
        ContainerDb(object_store, "Object Storage", "AWS S3", "Documents, reports, exports")
    }

    System_Ext(identity, "AWS Cognito", "Authentication & federation")
    System_Ext(gpu_infra, "GPU Infrastructure", "K8s/Slurm/Bare Metal")
    System_Ext(erp, "ERP System", "Invoicing")

    Rel(user, web_app, "Uses", "HTTPS")
    Rel(web_app, api_gateway, "API calls", "HTTPS/JSON")
    Rel(api_gateway, backend, "Routes requests", "HTTP")
    Rel(backend, db, "Reads/writes", "asyncpg")
    Rel(backend, cache, "Caches/sessions", "Redis protocol")
    Rel(backend, event_bus, "Publishes events", "AWS SDK")
    Rel(backend, object_store, "Stores files", "AWS SDK")
    Rel(event_bus, worker, "Triggers", "SQS subscription")
    Rel(worker, db, "Reads/writes", "asyncpg")
    Rel(backend, identity, "Validates tokens", "OIDC")
    Rel(worker, gpu_infra, "Provisions", "API calls")
    Rel(worker, erp, "Sends invoices", "API/webhook")
```

---

## Level 3: Component Diagram (Backend Modular Monolith)

```mermaid
C4Component
    title NeoCloud Backend - Bounded Contexts (Modular Monolith)

    Container_Boundary(backend, "Backend API - FastAPI") {

        Component(customers, "Customer Module", "Bounded Context", "Customer CRUD, contacts, billing accounts, hierarchy")
        Component(catalog, "Catalog & Pricing Module", "Bounded Context", "SKUs, price books, pricing models, rate cards")
        Component(sales, "Sales Module", "Bounded Context", "Opportunities, capacity checks, quotes")
        Component(contracts, "Contract Module", "Bounded Context", "Contracts, items, commitments, SLA, pricing agreements")
        Component(inventory, "Inventory Module", "Bounded Context", "Regions, DCs, clusters, racks, servers, GPUs")
        Component(capacity, "Capacity Module", "Bounded Context", "Capacity ledger, availability, incoming, overselling control")
        Component(reservations, "Reservation Module", "Bounded Context", "Reservation lifecycle, conflict detection")
        Component(allocations, "Allocation Module", "Bounded Context", "Physical resource binding, replacement")
        Component(iam, "IAM Module", "Bounded Context", "Users, roles, permissions, RBAC enforcement")
        Component(audit, "Audit Module", "Cross-cutting", "Audit trail, change logging")
        Component(dashboards, "Dashboard Module", "Read Model", "Aggregated views, KPIs, executive reports")
        Component(notifications, "Notification Module", "Cross-cutting", "Email, webhook, in-app notifications")
        Component(common, "Common/Shared", "Infrastructure", "DB, cache, auth middleware, event bus client")
    }

    ContainerDb(db, "PostgreSQL", "Aurora")
    Container(events, "EventBridge", "Event Bus")
    ContainerDb(cache, "Redis", "ElastiCache")

    Rel(customers, db, "CRUD")
    Rel(catalog, db, "CRUD")
    Rel(sales, db, "CRUD")
    Rel(contracts, db, "CRUD")
    Rel(inventory, db, "CRUD")
    Rel(capacity, db, "Ledger writes")
    Rel(reservations, db, "CRUD")
    Rel(allocations, db, "CRUD")
    Rel(dashboards, db, "Read-only queries")
    Rel(dashboards, cache, "Cached aggregates")

    Rel(sales, capacity, "Checks availability")
    Rel(contracts, reservations, "Creates reservations")
    Rel(reservations, capacity, "Updates ledger")
    Rel(reservations, allocations, "Triggers allocation")
    Rel(allocations, inventory, "Binds to GPUs")
    Rel(allocations, capacity, "Updates ledger")

    Rel(contracts, events, "ContractActivated")
    Rel(reservations, events, "ReservationConfirmed")
    Rel(allocations, events, "AllocationCompleted")
    Rel(inventory, events, "GPUStatusChanged")
    Rel(capacity, events, "CapacityChanged")
```

---

## Deployment Diagram

```mermaid
C4Deployment
    title NeoCloud - AWS Deployment Architecture

    Deployment_Node(aws, "AWS", "us-east-1") {
        Deployment_Node(cdn, "Edge") {
            Deployment_Node(cf, "CloudFront") {
                Container(static, "Static Assets", "Next.js SSG/SSR")
            }
            Deployment_Node(waf_node, "WAF") {
                Container(waf, "AWS WAF", "Rate limiting, geo-blocking, OWASP rules")
            }
        }

        Deployment_Node(vpc, "VPC - 10.0.0.0/16") {
            Deployment_Node(public_subnet, "Public Subnets") {
                Container(alb, "Application Load Balancer", "TLS termination, routing")
            }

            Deployment_Node(private_subnet, "Private Subnets") {
                Deployment_Node(ecs, "ECS Cluster") {
                    Container(api_service, "API Service", "FastAPI containers x3", "Auto-scaling 2-10")
                    Container(worker_service, "Worker Service", "Celery containers x2", "Auto-scaling 1-5")
                }
            }

            Deployment_Node(data_subnet, "Data Subnets") {
                ContainerDb(aurora, "Aurora PostgreSQL", "Multi-AZ, r6g.xlarge", "Primary + 2 read replicas")
                ContainerDb(elasticache, "ElastiCache Redis", "Cluster mode, r6g.large", "2 nodes")
            }
        }

        Deployment_Node(managed, "Managed Services") {
            Container(cognito, "Cognito User Pool", "Auth + federation")
            Container(eventbridge, "EventBridge", "Domain event bus")
            Container(sqs, "SQS Queues", "Worker task queues")
            Container(s3, "S3 Buckets", "Documents, exports, backups")
            Container(secrets, "Secrets Manager", "DB creds, API keys")
            Container(kms, "KMS", "Encryption keys")
        }

        Deployment_Node(observability, "Observability") {
            Container(cloudwatch, "CloudWatch", "Logs, metrics, alarms")
            Container(xray, "X-Ray", "Distributed tracing")
        }
    }
```

---

## Domain Event Catalog

### Event Flow Between Bounded Contexts

```mermaid
graph LR
    subgraph Commercial
        A[Customer Module] -->|CustomerCreated| B[Sales Module]
        B -->|OpportunityWon| C[Contract Module]
    end

    subgraph Capacity_Flow
        C -->|ContractActivated| D[Reservation Module]
        D -->|ReservationConfirmed| E[Capacity Module]
        D -->|ReservationConfirmed| F[Allocation Module]
        F -->|AllocationCompleted| E
        F -->|AllocationFailed| D
    end

    subgraph Infrastructure
        G[Inventory Module] -->|GPUStatusChanged| E
        G -->|ServerOffline| F
        E -->|CapacityThresholdBreached| H[Notification Module]
    end

    subgraph Lifecycle
        C -->|ContractExpiring| H
        C -->|ContractTerminated| D
        D -->|ReservationExpired| F
        F -->|AllocationReleased| E
        F -->|AllocationReleased| G
    end
```

### Event Definitions

| Event | Source | Consumers | Payload |
|-------|--------|-----------|---------|
| `CustomerCreated` | Customer | Sales, Notifications | `{customer_id, name, account_owner_id}` |
| `CustomerStatusChanged` | Customer | Contracts, Sales | `{customer_id, old_status, new_status}` |
| `OpportunityStageChanged` | Sales | Notifications, Dashboards | `{opportunity_id, customer_id, old_stage, new_stage, expected_mrr}` |
| `OpportunityWon` | Sales | Contracts | `{opportunity_id, customer_id, quote_id}` |
| `CapacityCheckCompleted` | Sales | Dashboards | `{check_id, opportunity_id, result, gap}` |
| `QuoteAccepted` | Sales | Contracts | `{quote_id, opportunity_id, customer_id}` |
| `ContractActivated` | Contracts | Reservations, Capacity, Notifications | `{contract_id, customer_id, items[], start_date}` |
| `ContractExpiring` | Contracts | Notifications, Sales | `{contract_id, customer_id, end_date, days_remaining}` |
| `ContractTerminated` | Contracts | Reservations, Allocations, Capacity | `{contract_id, customer_id, reason, effective_date}` |
| `ContractAmended` | Contracts | Reservations, Capacity | `{contract_id, changes[]}` |
| `ReservationCreated` | Reservations | Capacity, Notifications | `{reservation_id, contract_id, gpu_model, quantity, region}` |
| `ReservationConfirmed` | Reservations | Allocations, Capacity | `{reservation_id, contract_id, gpu_model, quantity}` |
| `ReservationExpired` | Reservations | Allocations, Capacity | `{reservation_id, contract_id}` |
| `ReservationCancelled` | Reservations | Capacity, Notifications | `{reservation_id, contract_id, reason}` |
| `AllocationRequested` | Allocations | Inventory | `{allocation_id, reservation_id, gpu_model, quantity, cluster_id}` |
| `AllocationCompleted` | Allocations | Capacity, Notifications, Dashboards | `{allocation_id, reservation_id, gpu_ids[], server_ids[]}` |
| `AllocationFailed` | Allocations | Reservations, Notifications | `{allocation_id, reservation_id, reason}` |
| `AllocationReleased` | Allocations | Capacity, Inventory | `{allocation_id, gpu_ids[], reason}` |
| `GPUStatusChanged` | Inventory | Capacity, Allocations | `{gpu_id, old_status, new_status, server_id}` |
| `ServerStatusChanged` | Inventory | Capacity, Allocations | `{server_id, old_status, new_status, gpu_ids[]}` |
| `IncomingCapacityUpdated` | Capacity | Sales, Dashboards, Notifications | `{gpu_model, quantity, region, expected_date, status}` |
| `CapacityThresholdBreached` | Capacity | Notifications, Sales | `{gpu_model, region, available, threshold_pct}` |
| `CapacityOversellAttempt` | Capacity | Notifications, Sales | `{gpu_model, region, requested, available, gap}` |

### Event Bus Configuration

```yaml
# EventBridge Bus
bus_name: neocloud-domain-events

# Rules route events to SQS queues per consumer
rules:
  - name: capacity-events
    pattern:
      source: ["neocloud.reservations", "neocloud.allocations", "neocloud.inventory"]
    target: sqs://neocloud-capacity-queue

  - name: allocation-events
    pattern:
      source: ["neocloud.reservations", "neocloud.inventory"]
      detail-type: ["ReservationConfirmed", "GPUStatusChanged"]
    target: sqs://neocloud-allocation-queue

  - name: notification-events
    pattern:
      detail-type:
        - prefix: "Contract"
        - prefix: "Capacity"
        - suffix: "Failed"
    target: sqs://neocloud-notification-queue

  - name: dashboard-events
    pattern:
      source:
        - prefix: "neocloud."
    target: sqs://neocloud-dashboard-queue
```

---

## Cross-Cutting Concerns

### Authentication & Authorization Flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant ALB as ALB
    participant API as FastAPI
    participant Cognito as Cognito
    participant DB as PostgreSQL

    U->>FE: Login
    FE->>Cognito: Authenticate (username/password or SSO)
    Cognito-->>FE: JWT (access + refresh tokens)
    FE->>ALB: API Request + Bearer token
    ALB->>API: Forward request
    API->>API: Validate JWT signature (cached JWKS)
    API->>DB: Load user roles & permissions
    API->>API: Check RBAC (resource + action)
    API->>API: Check tenant isolation (customer_id match)
    API-->>FE: Response (200 or 403)
```

### Audit Trail Flow

```mermaid
sequenceDiagram
    participant API as FastAPI Route
    participant Middleware as Audit Middleware
    participant Service as Business Logic
    participant DB as PostgreSQL
    participant Events as EventBridge

    API->>Middleware: Intercept request
    Middleware->>Middleware: Capture: user, IP, correlation_id
    Middleware->>Service: Pass through
    Service->>DB: Execute mutation
    DB-->>Service: Result + old/new values
    Service-->>Middleware: Return result
    Middleware->>DB: Write AuditLog entry
    Middleware->>Events: Publish audit event (async)
    Middleware-->>API: Return response
```

---

## Network Security Architecture

```
Internet
    │
    ▼
CloudFront (CDN + WAF)
    │
    ▼ (HTTPS only)
ALB (Public Subnet)
    │ Security Group: allow 443 from CloudFront IPs only
    ▼
ECS Tasks (Private Subnet)
    │ Security Group: allow from ALB SG only
    │
    ├──▶ Aurora (Data Subnet) — SG: allow 5432 from ECS SG
    ├──▶ ElastiCache (Data Subnet) — SG: allow 6379 from ECS SG
    └──▶ VPC Endpoints (S3, EventBridge, Secrets Manager, SQS)

No public IPs on any compute or data resources.
NAT Gateway for outbound (Cognito JWKS, external webhooks).
```
