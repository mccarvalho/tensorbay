# NeoCloud Platform — Frontend Improvement Roadmap

Tracks the UI/UX improvements that surface the (already rich) backend. The
backend exposes **118 endpoints across 10 domains**; the first-pass UI only
surfaced a thin list+create slice of each. This roadmap closes that gap,
mapped to the product plan's Release-1 EPICs.

Legend: ✅ done · 🚧 in progress · ⬜ planned

---

## In progress

### 1. Sales Pipeline UI — EPIC D / plan §9  🚧
The full commercial funnel: **Opportunity → Capacity Check → Quote (line items)**.
- Opportunities list + pipeline-stage KPIs (by `SalesStage`)
- Create/edit opportunity — supports **GPU and server** units (per decision)
- **Capacity Check** gate before quoting (`/v1/capacity/check`)
- Quotes per opportunity with line items (SKU picker from `/v1/catalog/skus`)
- Backend: `/v1/sales/opportunities` (CRUD), `/v1/sales/quotes` (CRUD) — already live

---

## Done

### CRM — Contacts + Activity timeline (pre-proposal control)  ✅
- Customer detail page /customers/:id with Contacts CRUD + Activity timeline
- New backend 'activities' table (CALL/EMAIL/MEETING/NOTE/DEMO/OTHER) + nested REST + migration
- Next-follow-up banner with overdue highlighting

## Planned (tracked, not lost)

### 2. Product Catalog & Pricing UI — EPIC C / plan §8  ✅ (SKUs, price books, prices; write-gated by pricing.write)
- SKU management (GPU/SERVER/CLUSTER/STORAGE/NETWORK)
- Price books (LIST/REGIONAL/CUSTOMER/CONTRACT/PROMO/RESERVED/SPOT)
- Customer-specific & contract-specific pricing
- Backend: `/v1/catalog/*` (15 endpoints) — already live, **no UI yet**

### 3. Executive Dashboard rebuild — EPIC J / plan §17  ⬜
Multi-section: **Fleet / Utilization / Finance / Sales** with charts (recharts).
- Fleet: installed/operational/available/reserved/allocated/maintenance, failure rate
- Finance: MRR, ARR, contracted ARR, revenue backlog, revenue/GPU, margin
- Sales: pipeline GPU demand, weighted demand, capacity gap
- Backend: `/v1/dashboards/*` (5 endpoints) — may need aggregate endpoints

### 4. Entity detail / drill-down pages — plan §22 data model  ⬜
- Customer → contacts, billing account, contracts, opportunities
- Contract → items, commitments, price agreements, reservations, allocations
- Opportunity → quotes
- Turns flat lists into a navigable system

### 5. Capacity timeline + overselling view — EPIC G / plan §12  ⬜
- NOTE: Inventory full CRUD (6 tiers) + Capacity incoming CRUD + GPU model comboboxes ✅ (finished this round); timeline/overselling-chart visualization still pending
- Visual capacity ledger (physical → operational → reserved → allocated → available)
- Incoming capacity + capacity timeline (months)
- Overselling gap visualization
- Backend: `/v1/capacity/*` (7 endpoints) — ledger/check live

### 6. Allocation workflow — EPIC I / plan §13  ⬜
- Reservation → allocate to cluster / servers / GPUs
- Allocation status lifecycle, replace/release resources
- Links commercial commitment to physical hardware

### 7. Cross-cutting UX polish — NFR / plan §34  ⬜
- Search/filter on every list, pagination controls
- Edit + delete actions (most pages are create-only today)
- Toasts, optimistic updates, richer loading/empty states
- Charts library (recharts) adopted in #3

---

## Decisions captured
- **Sales unit:** both GPU and server (opportunity/quote support both).
- **Charts:** deferred — focus is the Sales Pipeline this round; recharts lands with #3.
- **Order:** start with #1 (Sales), keep #2–#7 tracked here.
