# NeoCloud GPU Control Platform

## Product Plan v1.0

**Status:** Initial Product Planning\
**Objective:** Build a proprietary platform to manage the commercial,
operational, and financial lifecycle of a GPU infrastructure startup,
with a planned evolution into a full NeoCloud.

------------------------------------------------------------------------

## 1. Executive Summary

The **NeoCloud GPU Control Platform** will be the central system for
managing the entire commercial and operational lifecycle of GPU
infrastructure:

**Customer → Opportunity → Quote → Contract → Capacity → Reservation →
Allocation → Provisioning → Usage → Billing → Revenue/Margin**

The product should initially operate as a **Commercial & Capacity
Control Plane**, enabling the company to manage inventory, contracts,
capacity, and GPU commercialization. In subsequent releases, it will
evolve into an **Infrastructure Control Plane** integrated with the
physical infrastructure and, ultimately, into a NeoCloud platform with a
self-service portal, APIs, metering, and automated billing.

The core principle of the model is to keep four concepts separate:

1.  **Physical GPU / physical resource**
2.  **Commercial capacity**
3.  **Contract / commercial commitment**
4.  **Usage / billing**

This separation allows the same infrastructure to be commercialized
through different models---dedicated GPU, dedicated server, GPU-hour,
reserved capacity, private cluster, or, in the future,
instances/vGPU---without coupling the commercial model to the underlying
hardware.

------------------------------------------------------------------------

# 2. Product Vision

## 2.1 Product Vision

Build a proprietary platform capable of managing the complete
commercial, operational, and financial lifecycle of GPU infrastructure
and progressively becoming the **Cloud Management Platform** of the
NeoCloud.

## 2.2 Strategic Objectives

1.  Establish a single, reliable source of truth for GPU inventory and
    capacity.
2.  Prevent capacity overselling.
3.  Link physical resources to customers, contracts, and revenue.
4.  Support commercial reservations without prematurely binding them to
    specific hardware.
5.  Automate allocation and provisioning.
6.  Measure actual infrastructure usage.
7.  Automate pricing, commitments, and billing.
8.  Provide customers with a portal and APIs.
9.  Measure utilization, revenue, cost, margin, and payback per GPU.
10. Scale from hundreds to tens of thousands of GPUs.
11. Create proprietary technological IP for the NeoCloud.
12. Use commercial and operational data to support CAPEX decisions.

------------------------------------------------------------------------

# 3. Product Principles

## 3.1 Separation Between Physical Assets and Commercial Products

A physical H200 GPU is not necessarily a commercial product. A server
with 8 GPUs may be sold as:

-   8 dedicated GPUs;
-   1 dedicated server;
-   GPU-hours;
-   reserved capacity;
-   a private cluster;
-   Kubernetes GPU capacity;
-   eventually, vGPU or GPU instances.

Therefore, **Asset**, **Capacity Unit**, **SKU**, **Reservation**, and
**Allocation** must be independent entities.

## 3.2 Contract-First

The contract should be a central platform entity. Pricing, commitments,
SLA, term, reserved capacity, usage, and billing must all be traceable
back to a contract.

## 3.3 Ledger-Based

Capacity, usage, and billing should rely on historical/auditable records
so that subsequent changes do not destroy operational or financial
history.

## 3.4 API-First

Business capabilities should be exposed through internal APIs from the
beginning, preparing the platform for portals, integrations, and
self-service.

## 3.5 Modular Monolith First

The first version should avoid premature microservices. The backend can
begin as a **modular monolith**, with clearly defined bounded contexts
and event-driven communication where appropriate.

------------------------------------------------------------------------

# 4. Three-Layer Conceptual Architecture

``` text
NEOCLOUD PLATFORM

01 — BUSINESS CONTROL PLANE
Customers / Opportunities / Quotes / Contracts / Pricing / Billing / FinOps

02 — INFRASTRUCTURE CONTROL PLANE
Inventory / Capacity / Reservation / Allocation / Provisioning / Operations

03 — CUSTOMER CLOUD
Portal / API / GPU Instances / Clusters / Usage / Billing
```

Expected evolution:

``` text
Commercial Control
        ↓
Capacity Control
        ↓
Infrastructure Control
        ↓
Metering & Billing
        ↓
Customer Self-Service
        ↓
NeoCloud Platform
```

------------------------------------------------------------------------

# 5. Personas

  -----------------------------------------------------------------------
  Persona                 Responsibility          Primary Need
  ----------------------- ----------------------- -----------------------
  Executive               CEO/CFO/Board           Revenue, margin,
                                                  utilization, backlog,
                                                  forecast

  Sales Manager           Sales management        Capacity, pipeline,
                                                  pricing, contracts

  Sales                   Commercialization       Availability, quotes,
                                                  and reservations

  Operations              NOC/Infrastructure      GPUs, servers,
                                                  clusters, failures

  Cloud Admin             Platform                Allocation,
                                                  provisioning, and
                                                  operations

  Finance / FinOps        Finance                 Billing, commitments,
                                                  credits, margin

  Procurement             Acquisition             Future demand, capacity
                                                  gap, CAPEX

  Customer Admin          Customer                Resources, users,
                                                  usage, and costs

  Customer User           Customer                Instances, clusters,
                                                  and utilization
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 6. Platform Domains

``` text
GPU NEOCLOUD PLATFORM
│
├── 01. Customer Management
├── 02. Product Catalog & Pricing
├── 03. Sales & Opportunity Management
├── 04. Contract Management
├── 05. GPU Asset Inventory
├── 06. Capacity Management
├── 07. Reservation & Allocation
├── 08. Provisioning & Operations
├── 09. Metering & Usage Ledger
├── 10. Billing
├── 11. FinOps & Analytics
└── 12. Customer Portal & API
```

Cross-cutting layers:

-   IAM / RBAC;
-   Audit Trail;
-   Observability;
-   Notifications;
-   Integration;
-   Data Platform;
-   Security;
-   Configuration Management.

------------------------------------------------------------------------

# 7. EPIC 01 --- Customer Management

## Objective

Maintain customer master data and billing structures.

## Features

### Customer

-   Legal name;
-   Trading name;
-   Tax ID;
-   Country;
-   Currency;
-   Customer status;
-   Credit status;
-   Account owner;
-   Industry;
-   Parent company;
-   Commercial metadata.

### Contacts

-   Commercial;
-   Technical;
-   Finance;
-   Billing;
-   Executive sponsor.

### Billing Account

-   Billing address;
-   Currency;
-   Payment terms;
-   Tax configuration;
-   Credit limit;
-   Invoice preferences.

### Customer Hierarchy

``` text
Customer Group
   ├── Company US
   ├── Company Brazil
   └── Company Europe
```

### Sample User Story

> As a Sales Manager, I want to create a customer and its billing
> account so that contracts and GPU capacity can be associated with the
> correct commercial entity.

------------------------------------------------------------------------

# 8. EPIC 02 --- Product Catalog & Pricing

## Objective

Decouple hardware, capacity, and commercial offerings.

## SKU Examples

``` text
GPU-H100-SXM
GPU-H200-SXM
GPU-B200
SERVER-8X-H200
PRIVATE-CLUSTER-H200
STORAGE-NVME
NETWORK-EGRESS
```

## Supported Commercial Models

  ---------------------------------------------------------------------------
  Model                               Example
  ----------------------------------- ---------------------------------------
  GPU Hourly                          US$/GPU/hour |
                                      | GPU Monthly | US$/GPU/month

  Server Hourly                       US$/server/hour |
                                      | Dedicated Server | US$/server/month

  Reserved Capacity                   Capacity reserved for a defined period

  Commitment                          Minimum monthly spend

  Prepaid                             Prepaid credits

  Spot                                Variable pricing

  Private Cluster                     Dedicated cluster

  Tiered                              Usage-tier pricing

  Enterprise                          Negotiated terms

  Revenue Share                       Percentage of revenue
  ---------------------------------------------------------------------------

## Price Books

The system should support:

-   List Price;
-   regional pricing;
-   customer-specific pricing;
-   contract-specific pricing;
-   promotional pricing;
-   reserved pricing;
-   spot pricing.

Example:

``` text
SKU: GPU-H200-SXM

List Price:            $3.10/GPU-hour
Customer A:            $2.45/GPU-hour
Customer B:            $2.20/GPU-hour
Spot:                  $1.75/GPU-hour
12-month Reserved:     $2.10/GPU-hour
```

------------------------------------------------------------------------

# 9. EPIC 03 --- Sales & Opportunity Management

## Objective

Connect the commercial pipeline to current and future infrastructure
availability.

## Opportunity

Main fields:

-   Customer;
-   GPU model / SKU;
-   Quantity;
-   Expected start;
-   Duration;
-   Commercial model;
-   Expected MRR;
-   Probability;
-   Sales stage;
-   Account owner.

Example:

``` text
Customer: AI Corp
GPU: H200
Quantity: 256
Start: Nov/2026
Duration: 12 months
Expected MRR: $410K
Probability: 70%
```

## Capacity Check

Before issuing a quote, the system should allow Sales to verify
capacity.

``` text
Requested:          256 H200
Available:          192 H200
Incoming Capacity:  128 H200 on Nov 15
Result:             PARTIALLY AVAILABLE
```

The Capacity Check should consider:

-   current capacity;
-   existing reservations;
-   future contracts;
-   scheduled maintenance;
-   incoming capacity;
-   requested period;
-   region/datacenter;
-   GPU model;
-   technical constraints.

## Quote

An opportunity may generate one or more quotes containing:

-   items;
-   quantities;
-   prices;
-   discounts;
-   term;
-   commitment;
-   SLA;
-   commercial terms;
-   quote validity.

Flow:

``` text
Opportunity
    ↓
Capacity Check
    ↓
Quote
    ↓
Contract
```

------------------------------------------------------------------------

# 10. EPIC 04 --- Contract Management

## Objective

Manage commercial commitments and associate them with capacity.

## Structure

``` text
Customer
   └── Contract
        ├── Contract Item
        ├── Price Agreement
        ├── Commitment
        ├── SLA
        ├── Reservation
        ├── Allocation
        └── Billing Rules
```

## Example

``` text
Customer: AI Company Inc.
Contract: CTR-2026-00124
Term: 12 months
Commitment: 128 × H200
Price: US$ 2.25/GPU-hour
Minimum Monthly Commitment: US$ 207,360
Storage: 20 TB
Network: 50 TB/month
Start: Sep 1, 2026
End: Aug 31, 2027
```

## Features

-   Contract lifecycle;
-   amendments;
-   renewals;
-   termination;
-   contract items;
-   pricing agreements;
-   commitments;
-   SLA;
-   start/end dates;
-   auto-renewal;
-   commercial notes;
-   document references;
-   contract status;
-   reservation generation.

------------------------------------------------------------------------

# 11. EPIC 05 --- GPU Asset Inventory

## Objective

Manage physical inventory and its lifecycle.

## Hierarchy

``` text
Region
 └── Datacenter
      └── Cluster
           └── Rack
                └── Server
                     ├── GPU 01
                     ├── GPU 02
                     ├── ...
                     └── GPU 08
```

## GPU Asset

Recommended fields:

  Field              Example
  ------------------ ------------------
  GPU ID             GPU-US-FL-000342
  Manufacturer       NVIDIA
  Model              H200 SXM
  Memory             141 GB
  Serial Number      XXXXX
  Server             SRV-0042
  Rack               RACK-21
  Cluster            H200-CLUSTER-01
  Datacenter         DC-MIA-01
  Acquisition Cost   US\$ X
  Acquisition Date   2026-08-01
  Supplier           Vendor X
  Warranty           3 years

## Operational Status

``` text
ONLINE
OFFLINE
MAINTENANCE
FAILED
DECOMMISSIONED
```

## Commercial Status

``` text
AVAILABLE
RESERVED
ALLOCATED
```

These states must remain separate.

------------------------------------------------------------------------

# 12. EPIC 06 --- Capacity Management

## Objective

Create a reliable view of current and future commercial capacity.

## Capacity Ledger

Example:

``` text
H200

Physical                   2,048
Offline                       32
Maintenance                    8
────────────────────────────────
Operational                2,008

Allocated                  1,420
Reserved                     256
────────────────────────────────
Commercial Available         332
```

## Concepts

-   Physical Capacity;
-   Operational Capacity;
-   Reserved Capacity;
-   Allocated Capacity;
-   Available Capacity;
-   Incoming Capacity;
-   Future Committed Capacity.

## Future Capacity

``` text
Purchase Order: 512 B200
Expected Delivery: Nov 15, 2026
Expected Operational: Dec 1, 2026
```

## Capacity Timeline

``` text
             SEP    OCT    NOV    DEC    JAN
H200 Total   1000   1000   1200   1200   1600
Contracted    720    810    900    940   1100
Available     280    190    300    260    500
```

## Overselling Prevention

When attempting to sell:

``` text
Requested:       256 H200
Available:       180 H200
Capacity Gap:     76 H200
Full Capacity:   Dec 15, 2026
```

The system should alert or block the commitment according to commercial
policy.

------------------------------------------------------------------------

# 13. EPIC 07 --- Reservation & Allocation

## Reservation

Represents the **commercial capacity commitment**, without requiring
specific physical hardware to be selected in advance.

Example:

> Customer A is entitled to 128 H200 GPUs starting Oct 1, 2026.

## Allocation

Represents the physical/logical association between contracted capacity
and infrastructure.

``` text
Contract CTR-123
      ↓
Reservation
128 H200
      ↓
Allocation
      ↓
Cluster H200-02
      ↓
16 Servers
      ↓
128 GPUs
```

This separation allows hardware to be replaced without changing the
contract.

## Allocation Status

``` text
AVAILABLE
RESERVED
PROVISIONING
ALLOCATED
IN_USE
MAINTENANCE
FAILED
RELEASED
DECOMMISSIONED
```

------------------------------------------------------------------------

# 14. EPIC 08 --- Provisioning & Operations

## Objective

Convert a commercial allocation into usable compute resources.

``` text
Allocation
     ↓
Provisioning Request
     ↓
Provisioning Orchestrator
     ├── Kubernetes
     ├── Slurm
     └── Bare Metal
```

## Provisioning Request

Should contain:

-   customer;
-   contract;
-   reservation/allocation;
-   GPU type;
-   quantity;
-   region;
-   cluster;
-   image;
-   network;
-   storage;
-   provisioning mode;
-   requester;
-   status.

## API Evolution

``` http
POST /v1/instances
```

Conceptual example:

``` json
{
  "gpu": "H200",
  "quantity": 8,
  "region": "us-east",
  "image": "pytorch"
}
```

## Operations

-   Provision;
-   Start;
-   Stop;
-   Reboot;
-   Resize, where applicable;
-   Reimage;
-   Release;
-   Maintenance;
-   Replace failed hardware.

------------------------------------------------------------------------

# 15. EPIC 09 --- Metering & Usage Ledger

## Objective

Create a reliable, auditable layer between infrastructure telemetry and
billing.

``` text
Infrastructure
     ↓
Telemetry Collectors
     ↓
Normalization
     ↓
Usage Events
     ↓
Immutable Usage Ledger
     ├── Billing
     ├── Customer Portal
     └── FinOps
```

## Metrics

-   GPU seconds/hours;
-   CPU seconds;
-   RAM GB-seconds;
-   Storage GB-hours;
-   Network ingress;
-   Network egress;
-   IP/resource hours;
-   additional services.

## Usage Event

Conceptual fields:

``` text
customer_id
contract_id
allocation_id
resource_id
sku_id
timestamp_start
timestamp_end
gpu_seconds
cpu_seconds
memory_gb_seconds
storage_gb_hours
network_ingress_gb
network_egress_gb
```

## Ledger Requirements

-   logical immutability;
-   idempotency;
-   deduplication;
-   traceability;
-   correction versioning;
-   reconciliation;
-   retention;
-   auditability.

------------------------------------------------------------------------

# 16. EPIC 10 --- Billing

## Objective

Convert contract + price + commitment + usage into billable amounts.

``` text
Usage Ledger
      +
Contract
      +
Price Book
      +
Commitment
      +
Credits
      +
Discounts
      ↓
Billing Engine
      ↓
Billing Statement
      ↓
Invoice / ERP Integration
```

## Models

### Usage Based

``` text
GPU Hours × Contract Price
```

### Committed Spend

``` text
MAX(Actual Usage, Minimum Commitment)
```

### Reserved GPU

``` text
Reserved Quantity × Monthly Price
```

### Prepaid

``` text
Usage → Debit Credit Balance
```

### Hybrid

``` text
Commitment + Overage
```

## Example

``` text
Customer: ABC AI
Billing Period: August

GPU Usage
85,420 GPU-hours × $2.25       $192,195

Storage                          $1,200
Network Egress                   $1,440
────────────────────────────────────────
Usage Subtotal                 $194,835

Minimum Commitment             $200,000
────────────────────────────────────────
Billable Amount                $200,000
```

------------------------------------------------------------------------

# 17. EPIC 11 --- FinOps & Analytics

## Executive Dashboard

### Fleet

-   Installed GPUs;
-   Operational GPUs;
-   Available GPUs;
-   Reserved GPUs;
-   Allocated GPUs;
-   GPUs under maintenance;
-   failure rate.

### Utilization

-   Physical utilization;
-   Commercial utilization;
-   Revenue utilization;
-   utilization by GPU model;
-   utilization by datacenter;
-   utilization by customer.

### Finance

-   MRR;
-   ARR;
-   Contracted ARR;
-   Revenue Backlog;
-   Revenue/GPU;
-   Cost/GPU;
-   Revenue/GPU-hour;
-   Gross Margin;
-   CAPEX deployed;
-   payback.

### Sales

-   Pipeline GPU demand;
-   weighted pipeline demand;
-   capacity requested;
-   available capacity;
-   future capacity;
-   capacity gap.

------------------------------------------------------------------------

# 18. Unit Economics

The system should calculate unit economics by:

-   GPU model;
-   server;
-   cluster;
-   datacenter;
-   customer;
-   contract;
-   SKU.

Example:

``` text
H200

Monthly Costs
  Depreciation
  Energy
  Datacenter
  Network
  Operations
  Financing
────────────────────────
Total GPU Cost          $1,420

Revenue/GPU             $2,310
Gross Profit              $890
Gross Margin             38.5%
```

## Indicators

### Break-Even Utilization

Minimum utilization required to cover the cost of the asset.

### CAPEX Payback

Estimated time required to recover the investment.

### Revenue Efficiency

``` text
Revenue Generated
────────────────────────
Available GPU-hours
```

### Margin by GPU Model

  GPU        Qty   Utilization   Revenue/month   Cost/month   Margin
  ------ ------- ------------- --------------- ------------ --------
  H100       512           92%          \$1.1M       \$620K      44%
  H200     1,024           81%          \$2.4M      \$1.48M      38%
  B200       256           68%          \$890K       \$610K      31%

------------------------------------------------------------------------

# 19. EPIC 12 --- Customer Portal & Public API

## Portal

``` text
CUSTOMER PORTAL

Overview

Running GPUs          128
GPU Utilization       87%

Current Month
GPU Hours          71,820
Estimated Bill     $157,300
Credits             $82,400

Resources
Clusters
Instances
Storage
Network

Billing
Usage
Invoices

API Keys
Users
```

## Features

-   Dashboard;
-   resource inventory;
-   cluster/instance management;
-   usage;
-   estimated bill;
-   invoices;
-   credit balance;
-   API keys;
-   user management;
-   notifications;
-   support integration.

## API

The public API should progressively expose:

-   resources;
-   capacity;
-   provisioning;
-   instances;
-   clusters;
-   usage;
-   billing;
-   API keys.

------------------------------------------------------------------------

# 20. IAM and RBAC

## Initial Roles

``` text
SUPER_ADMIN
EXECUTIVE
SALES_MANAGER
SALES
FINANCE
OPERATIONS_MANAGER
OPERATIONS
CLOUD_ADMIN
CUSTOMER_ADMIN
CUSTOMER_USER
```

## Granular Permissions

``` text
customer.read
customer.write

contract.read
contract.write

inventory.read
inventory.write

capacity.read

pricing.read
pricing.write

billing.read
billing.write

allocation.create
allocation.release

provisioning.execute
```

Customer access must be tenant-aware and prevent cross-tenant access.

------------------------------------------------------------------------

# 21. Audit Trail

Every sensitive change should record:

``` text
WHO
WHEN
ACTION
ENTITY
ENTITY ID
OLD VALUE
NEW VALUE
SOURCE
IP / SESSION
CORRELATION ID
```

Mandatory auditing for:

-   prices;
-   contracts;
-   amendments;
-   reservations;
-   allocations;
-   credits;
-   billing;
-   invoices;
-   capacity;
-   IAM;
-   permissions;
-   administrative operations.

------------------------------------------------------------------------

# 22. Conceptual Data Model

``` text
CUSTOMER
   │
   ├── CONTACT
   ├── BILLING_ACCOUNT
   ├── OPPORTUNITY
   │      └── QUOTE
   │
   ├── CONTRACT
   │      ├── CONTRACT_ITEM
   │      │      └── SKU
   │      ├── PRICE_AGREEMENT
   │      ├── COMMITMENT
   │      ├── SLA
   │      ├── RESERVATION
   │      │      └── ALLOCATION
   │      └── BILLING_RULE
   │
   └── USER


REGION
   └── DATACENTER
        └── CLUSTER
             └── RACK
                  └── SERVER
                       └── GPU


ALLOCATION
   └── RESOURCE
        └── USAGE_EVENT
             └── USAGE_LEDGER


USAGE_LEDGER
   └── BILLING_LINE
        └── BILLING_STATEMENT
             └── INVOICE
```

------------------------------------------------------------------------

# 23. Logical Architecture

``` text
                       Web / Customer Portal
                                │
                           API Gateway
                                │
                       ┌────────▼────────┐
                       │  Control Plane  │
                       └────────┬────────┘
                                │
     ┌────────────┬─────────────┼─────────────┬────────────┐
     │            │             │             │            │
 Commercial   Inventory      Capacity     Operations    Billing
     │            │             │             │            │
     └────────────┴─────────────┼─────────────┴────────────┘
                                │
                             Event Bus
                                │
             ┌──────────────────┼──────────────────┐
             │                  │                  │
          Metering         Provisioning        Analytics
             │                  │                  │
             ▼                  ▼                  ▼
       Usage Ledger       GPU Infrastructure    Data Lake
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
                Kubernetes   Slurm   Bare Metal
```

------------------------------------------------------------------------

# 24. Technology Strategy

  Component                    Initial Recommendation
  ---------------------------- ----------------------------------------------
  Frontend                     React / Next.js
  Backend                      Python + FastAPI
  Transactional DB             PostgreSQL / Amazon Aurora
  Cache                        Redis / ElastiCache
  API                          REST initially
  Event Bus                    Amazon EventBridge
  High-volume Streaming        MSK/Kafka when required
  Object Storage               Amazon S3
  Metering Data                S3 + streaming
  Analytics                    Athena initially; Redshift as scale requires
  Containers                   ECS initially / EKS as needed
  Infrastructure Integration   Kubernetes / Slurm / Bare Metal
  Identity                     Cognito + Enterprise Federation
  Secrets                      AWS Secrets Manager
  Observability                OpenTelemetry + CloudWatch
  IaC                          Terraform
  CI/CD                        GitHub Actions or AWS native
  Security                     IAM, KMS, WAF, GuardDuty, Security Hub

## Evolution Strategy

Do not start with dozens of microservices.

Use:

-   modular monolith;
-   bounded contexts;
-   internal APIs;
-   domain events;
-   outbox/idempotency patterns where required;
-   progressive separation of high-scale services.

Natural candidates for future separation:

-   Metering;
-   Billing;
-   Provisioning;
-   Capacity;
-   Notifications.

------------------------------------------------------------------------

# 25. Core APIs

Conceptual examples:

``` text
/v1/customers
/v1/opportunities
/v1/quotes
/v1/contracts
/v1/products
/v1/pricing
/v1/assets
/v1/gpus
/v1/servers
/v1/clusters
/v1/capacity
/v1/reservations
/v1/allocations
/v1/provisioning
/v1/usage
/v1/billing
/v1/invoices
/v1/credits
```

The API should incorporate:

-   authentication;
-   authorization;
-   tenant isolation;
-   pagination;
-   idempotency;
-   rate limiting;
-   correlation IDs;
-   versioning;
-   auditing.

------------------------------------------------------------------------

# 26. Roadmap

## Release 1 --- Commercial Control Plane / MVP

**Indicative timeline:** Weeks 1--10

### Deliverables

-   Customer Management;
-   Product Catalog;
-   basic Pricing;
-   Opportunity;
-   Contract Management;
-   GPU Inventory;
-   Region/Datacenter/Cluster/Rack/Server/GPU;
-   Capacity Management;
-   Reservation;
-   Allocation;
-   Capacity Check;
-   basic executive dashboard;
-   RBAC;
-   Audit Trail.

### Questions the MVP Must Answer

-   How many GPUs do we have?
-   Where are they?
-   How many are operational?
-   How many are available?
-   How many are reserved?
-   How many are allocated?
-   To which customer?
-   Under which contract?
-   For how long?
-   At what price?
-   When will they become available again?
-   How much future revenue is already contracted?
-   Do we have capacity for a new contract?

### Outcome

The startup can operate GPU commercialization in a structured and
controlled manner.

------------------------------------------------------------------------

# 27. Release 2 --- Infrastructure Operations

**Indicative timeline:** Weeks 11--18

### Deliverables

-   advanced capacity forecasting;
-   incoming capacity;
-   Purchase Orders / planned capacity;
-   provisioning requests;
-   cluster integration;
-   maintenance management;
-   hardware lifecycle;
-   alerts;
-   SLA;
-   operational dashboard;
-   allocation automation;
-   hardware replacement workflow.

### Outcome

The platform begins operating as an Infrastructure Control Plane.

------------------------------------------------------------------------

# 28. Release 3 --- Metering, Billing & FinOps

**Indicative timeline:** Weeks 19--28

### Deliverables

-   telemetry collectors;
-   usage normalization;
-   immutable Usage Ledger;
-   Pricing Engine;
-   commitments;
-   credits;
-   billing cycles;
-   Billing Engine;
-   statements;
-   invoice integration;
-   FinOps;
-   unit economics;
-   reconciliation;
-   billing audit.

### Outcome

The platform automatically connects infrastructure, usage, and revenue.

------------------------------------------------------------------------

# 29. Release 4 --- NeoCloud Customer Platform

**Indicative timeline:** Weeks 29--40

### Deliverables

-   Customer Portal;
-   Public API;
-   API Keys;
-   self-service provisioning;
-   Kubernetes integration;
-   Slurm integration;
-   bare-metal workflows;
-   GPU instances;
-   images;
-   customer usage dashboard;
-   billing portal;
-   tenant administration.

### Outcome

The platform evolves from an internal system into a customer-consumable
cloud platform.

------------------------------------------------------------------------

# 30. Recommended Team

  Role                                    Quantity
  --------------------------------- --------------
  Product Manager / Product Owner                1
  Solution / Software Architect                  1
  Senior Backend Engineer                        2
  Backend Engineer                               1
  Frontend Engineer                              2
  Cloud / Platform Engineer                      1
  Data Engineer                                  1
  QA / Automation Engineer                       1
  UX/UI Designer                               0.5
  **Approximate Total**               **10.5 FTE**

Starting with Release 3, consider adding specialized expertise in:

-   Billing;
-   FinOps;
-   GPU Infrastructure;
-   Slurm/Kubernetes;
-   Data Engineering.

------------------------------------------------------------------------

# 31. Preliminary Effort Estimate

  Release                         Estimated Effort
  ------------------------- ----------------------
  R1 --- Commercial MVP             3,500--4,500 h
  R2 --- Operations                 2,500--3,500 h
  R3 --- Metering/Billing           4,000--5,000 h
  R4 --- NeoCloud Portal            4,000--5,500 h
  **Total**                   **14,000--18,500 h**

These figures represent an order-of-magnitude estimate and should be
refined after decomposing the epics into features and user stories.

------------------------------------------------------------------------

# 32. KPIs

## Infrastructure

-   GPU Availability;
-   GPU Utilization;
-   Failed GPU %;
-   Capacity Coverage;
-   Maintenance Rate;
-   Capacity by GPU Model;
-   Capacity by Datacenter.

## Commercial

-   Contracted GPUs;
-   Reserved GPUs;
-   Pipeline GPU Demand;
-   Weighted GPU Demand;
-   Contracted ARR;
-   Revenue Backlog;
-   Average Contract Duration;
-   Average Selling Price / GPU-hour.

## Financial

-   Revenue/GPU;
-   Cost/GPU;
-   Revenue/GPU-hour;
-   Gross Margin/GPU;
-   Gross Margin/Customer;
-   Gross Margin/Contract;
-   CAPEX Payback;
-   Break-Even Utilization.

## Operational

-   Provisioning Time;
-   MTTR;
-   SLA Compliance;
-   Failed Provisioning Rate;
-   Resource Release Time.

------------------------------------------------------------------------

# 33. Capacity Intelligence

## Objective

Transform sales, contract, and infrastructure data into capacity
acquisition decisions.

``` text
Sales Pipeline ───────┐
Contracts ────────────┤
Historical Usage ─────┤
Incoming Hardware ────┼──► Forecast Engine
Pricing ──────────────┤          │
Churn ────────────────┤          ▼
Utilization ──────────┘    Capacity Forecast
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
                  Sales    Procurement   Finance
```

## Sample Recommendation

``` text
Forecast:
Capacity deficit of 384 H200 between Nov 15 and Jan 31.

Weighted pipeline demand:       612 GPUs
Projected available capacity:   228 GPUs
Projected gap:                  384 GPUs

Recommended procurement range:
384–512 GPUs
```

## Future Evolution

-   demand forecasting;
-   churn prediction;
-   dynamic pricing;
-   spot pricing;
-   optimal capacity allocation;
-   procurement recommendations;
-   datacenter capacity optimization;
-   margin-aware scheduling.

------------------------------------------------------------------------

# 34. Non-Functional Requirements

## Security

-   tenant isolation;
-   least privilege;
-   encryption at rest/in transit;
-   secrets management;
-   MFA for administrative roles;
-   audit trail;
-   secure API keys.

## Availability

Define progressive SLOs by release.

## Scalability

The design must support growth without requiring a complete redesign of
the domain model.

## Observability

-   logs;
-   metrics;
-   traces;
-   correlation IDs;
-   business metrics;
-   infrastructure metrics.

## Integrity

Special attention must be given to:

-   capacity transactions;
-   reservation conflicts;
-   usage deduplication;
-   billing reconciliation;
-   idempotency.

## Compliance

Prepare the architecture for enterprise controls and eventual SOC 2 /
ISO 27001 requirements.

------------------------------------------------------------------------

# 35. Backlog Structure

``` text
PRODUCT
   │
   ├── EPIC
   │     ├── FEATURE
   │     │      ├── USER STORY
   │     │      ├── USER STORY
   │     │      └── USER STORY
   │     └── FEATURE
   │
   └── EPIC
```

Each User Story should contain:

-   ID;
-   Epic;
-   Feature;
-   title;
-   description;
-   persona;
-   business value;
-   acceptance criteria;
-   priority;
-   dependencies;
-   release;
-   sprint;
-   estimate;
-   status.

## Prioritization

Initially use **MoSCoW**:

-   **Must Have**
-   **Should Have**
-   **Could Have**
-   **Won't Have Now**

------------------------------------------------------------------------

# 36. Release 1 Macro Backlog

## EPIC A --- Foundation

-   Project structure;
-   environments;
-   CI/CD;
-   authentication;
-   RBAC;
-   audit;
-   observability;
-   database baseline.

## EPIC B --- Customer

-   Customer CRUD;
-   contacts;
-   billing accounts;
-   customer hierarchy.

## EPIC C --- Product & Pricing

-   SKU;
-   GPU products;
-   price books;
-   customer pricing;
-   basic pricing models.

## EPIC D --- Sales

-   opportunities;
-   opportunity items;
-   capacity request;
-   capacity check;
-   quotes.

## EPIC E --- Contracts

-   contracts;
-   contract items;
-   commitments;
-   pricing agreements;
-   contract lifecycle.

## EPIC F --- Infrastructure Inventory

-   regions;
-   datacenters;
-   clusters;
-   racks;
-   servers;
-   GPUs;
-   operational/commercial status.

## EPIC G --- Capacity

-   capacity calculation;
-   capacity ledger;
-   availability;
-   future availability;
-   incoming capacity;
-   overselling control.

## EPIC H --- Reservation

-   create reservation;
-   reservation lifecycle;
-   conflict detection;
-   expiration/release.

## EPIC I --- Allocation

-   allocate resources;
-   allocation history;
-   replace resources;
-   release resources.

## EPIC J --- Dashboards

-   fleet;
-   capacity;
-   customer;
-   contract;
-   executive overview.

------------------------------------------------------------------------

# 37. MVP Success Criteria

The MVP will be considered operational when:

1.  100% of commercially available GPUs are registered and traceable.
2.  All commercial capacity can be classified as available, reserved, or
    allocated.
3.  Every reservation can be associated with a customer and contract.
4.  The system detects capacity conflicts.
5.  Sales can query current and future capacity.
6.  Operations can identify the hardware associated with an allocation.
7.  Executives can view capacity and contracted revenue.
8.  Sensitive changes are auditable.
9.  RBAC is implemented.
10. The model can evolve into metering and billing without fundamental
    restructuring.

------------------------------------------------------------------------

# 38. Architecture Decisions to Validate During Discovery

Before development, validate:

1.  Which GPU models will initially be commercialized?
2.  Will infrastructure be owned, colocated, or hybrid?
3.  Kubernetes, Slurm, bare metal, or a combination?
4.  Will the minimum sales unit be a GPU, a server, or both?
5.  Will Spot be available from the beginning?
6.  Which ERP/accounting system will receive invoices?
7.  Which CRM will be used?
8.  Will there be integrations with suppliers/datacenters?
9.  How will telemetry be collected?
10. What will the tenancy model be?
11. Which regions/datacenters will be available at launch?
12. What GPU volume is expected over the first 12, 24, and 36 months?
13. Will billing be USD-only or multi-currency?
14. Which tax jurisdictions must be supported?
15. Will a marketplace/reseller model be required?

------------------------------------------------------------------------

# 39. Key Risks

  -----------------------------------------------------------------------
  Risk                    Impact                  Mitigation
  ----------------------- ----------------------- -----------------------
  Coupling contracts      High                    Keep Reservation
  directly to hardware                            separate from
                                                  Allocation

  Overselling             High                    Capacity Ledger +
                                                  temporal capacity
                                                  checks

  Inconsistent billing    High                    Immutable Usage
                                                  Ledger + reconciliation

  Premature microservices Medium/High             Modular monolith

  Heterogeneous telemetry High                    Normalization layer

  Lack of auditability    High                    Audit Trail from MVP

  Incorrect capacity      High                    Separate confirmed
  forecasting                                     vs. weighted pipeline

  Excessive vendor        Medium                  Provisioning interfaces
  lock-in                                         and IaC

  Pricing complexity      High                    Decoupled Pricing
                                                  Engine

  Tenant data leakage     Critical                Tenant-aware
                                                  authorization and
                                                  testing
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 40. Next Steps

## Phase 1 --- Product Discovery

-   validate the commercial model;
-   validate physical infrastructure;
-   validate personas;
-   define current processes;
-   define the MVP boundary;
-   map integrations;
-   finalize non-functional requirements.

## Phase 2 --- Product Backlog

Decompose Release 1 into:

**10--12 epics → 40--60 features → 100+ user stories**

For each item:

-   MoSCoW priority;
-   acceptance criteria;
-   dependencies;
-   estimate;
-   sprint;
-   owner.

## Phase 3 --- Architecture Definition

Produce:

-   C4 Context;
-   C4 Container;
-   component architecture;
-   ERD;
-   event catalog;
-   API specification;
-   security architecture;
-   deployment architecture.

## Phase 4 --- UX

Produce wireframes for:

-   Executive Dashboard;
-   Sales Capacity;
-   Customer;
-   Contract;
-   Inventory;
-   Capacity;
-   Reservation;
-   Allocation;
-   Operations.

## Phase 5 --- Delivery Planning

Define:

-   squad;
-   sprint cadence;
-   environments;
-   Definition of Ready;
-   Definition of Done;
-   QA strategy;
-   release strategy;
-   observability;
-   security gates.

------------------------------------------------------------------------

# 41. Long-Term Vision

The desired evolution is to transform the system into a central part of
the company's technology value:

``` text
Internal Commercial System
          ↓
GPU Capacity Platform
          ↓
Infrastructure Control Plane
          ↓
Automated Metering & Billing
          ↓
Customer Self-Service Cloud
          ↓
Full NeoCloud Platform
```

At the final stage, the platform is no longer merely an administrative
system. It becomes the **software platform that operates the NeoCloud**,
connecting sales, contracts, infrastructure, usage, billing, and
capacity expansion decisions.

------------------------------------------------------------------------

## Conclusion

The proposed design enables the company to begin with an MVP focused on
the immediate business problem---**managing GPU commercialization,
inventory, and capacity by customer and contract**---without limiting
future evolution.

The most important architectural elements to establish from the first
release are:

-   separation between assets, capacity, reservations, and allocations;
-   Contract as a central entity;
-   Capacity Ledger;
-   overselling prevention;
-   RBAC and Audit Trail;
-   a data model prepared for Metering;
-   APIs and bounded contexts;
-   an architecture prepared for Kubernetes, Slurm, and bare-metal
    integration.

These decisions create the foundation for the product to evolve from a
**Commercial GPU Control Plane** into a **complete proprietary NeoCloud
platform**.
