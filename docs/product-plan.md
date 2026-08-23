# NeoCloud GPU Control Platform - Product Plan v1.0

Imported from initial product planning document.
See full source: uploads/1dff05ed5a4b4309bfd03ff189dd9b2f_NeoCloud_GPU_Product_Plan_EN.md

## Quick Reference

### Architecture Layers
1. Business Control Plane (Customers, Contracts, Pricing, Billing, FinOps)
2. Infrastructure Control Plane (Inventory, Capacity, Reservation, Allocation, Provisioning)
3. Customer Cloud (Portal, API, Instances, Clusters, Usage, Billing)

### Release Roadmap
- R1 (Weeks 1-10): Commercial Control Plane / MVP
- R2 (Weeks 11-18): Infrastructure Operations
- R3 (Weeks 19-28): Metering, Billing & FinOps
- R4 (Weeks 29-40): NeoCloud Customer Platform

### Tech Stack
- Frontend: React / Next.js
- Backend: Python + FastAPI
- DB: PostgreSQL / Aurora
- Cache: Redis / ElastiCache
- Events: EventBridge
- Storage: S3
- Containers: ECS → EKS
- IaC: Terraform
- CI/CD: GitHub Actions

### Core Principles
- Separation: Physical Asset ≠ Commercial Capacity ≠ Contract ≠ Usage
- Contract-First: All pricing, SLA, billing traces back to a contract
- Ledger-Based: Immutable, auditable records for capacity/usage/billing
- API-First: Internal APIs from day one
- Modular Monolith: Bounded contexts, progressive decomposition
