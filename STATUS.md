# NeoCloud — Status & What To Do When You're Back

_Last updated: 2026-10-17 (autonomous session while you were away)_

## TL;DR — the full application is live

| Layer | URL / Resource | Status |
|-------|----------------|--------|
| **Frontend (web UI)** | https://d22xy9yyfwju3n.cloudfront.net | ✅ Live (CloudFront + S3) |
| **API (backend)** | http://neocloud-dev-alb-1924778288.us-east-2.elb.amazonaws.com | ✅ Live (ECS Fargate) |
| **API docs** | …/docs (Swagger) | ✅ |
| **Database** | Aurora PostgreSQL (27 tables) | ✅ Migrated |
| **SSO** | Cognito + Google Workspace federation | ✅ Handshake validated |
| **AI documents** | Bedrock Claude | ⚠️ Blocked on 1 console form (see below) |

Everything was validated end-to-end: the SPA loads over HTTPS, SPA routing works,
SSO redirects to Google, and a full authenticated CRUD round-trip
(create → list → delete a customer, with audit trail) succeeded through the live API.

## What was built this session (the frontend)

A React + Vite + TypeScript SPA under `web/`, styled with the **TensorBay brand**
(deep-purple dark theme + cyan/purple accents from the Commission Plan deck, and the
official logo from tensorbay.io). It has:

- **Login** with "Sign in with Google" (Cognito hosted UI, PKCE auth-code flow)
- **Executive dashboard** (KPI cards in the deck's big-number layout)
- **Domain screens**: Customers, Contracts, Inventory, Capacity, Reservations
- **AI Documents** screen (MSA/LOI/Proposal/Contract generation + approve/reject)

Hosted on **S3 + CloudFront** (new Terraform module `modules/frontend`), with
**CI/CD** (`.github/workflows/cd-web.yml`) that auto-deploys on `web/**` pushes.

## ⚠️ ACTION REQUIRED FROM YOU (3 items)

### 1. Enable the Anthropic model (unblocks AI document generation)
The AI feature is fully wired but returns 500 because of a one-time AWS requirement.
The ECS logs show:
> `Model use case details have not been submitted for this account. Fill out the
> Anthropic use case details form before using the model.`

**Do this:** AWS Console → **Bedrock** (region **us-east-2**) → **Model access** →
Anthropic Claude → **submit the "use case details" form**. Wait ~15 minutes.
After that, `POST /v1/documents/generate` (and the AI Documents screen) will work
with no code changes. _(This is the only thing standing between you and working AI docs.)_

### 2. Rotate the Google OAuth client secret
The Google client secret was shared in chat, so treat it as exposed. In the
**Google Cloud Console → Credentials**, regenerate the client secret, then update it:
```bash
# edit infra/terraform/terraform.tfvars  -> google_oidc_client_secret = "NEW_SECRET"
cd infra/terraform && terraform apply
```
_(The creds now live in the gitignored `terraform.tfvars`, which also fixed an
earlier bug where the Google IdP was destroyed/recreated on every apply.)_

### 3. Confirm the Google consent screen is "Internal"
Google Cloud Console → **OAuth consent screen** → **User type = Internal**. This
restricts sign-in to your Google Workspace org only (otherwise any Google account
could authenticate).

## Try it now

1. Open **https://d22xy9yyfwju3n.cloudfront.net**
2. Click **Sign in with Google** → authenticate with your Workspace account
3. You'll land on the executive dashboard; navigate to Customers and create one
4. (AI Documents will work after item #1 above)

## Where things live

- Frontend: `web/` (see `web/README.md`)
- Backend: `app/` (see `app/README.md`)
- Infra: `infra/terraform/` (see `infra/terraform/README.md`)
- CI/CD: `.github/workflows/` — `ci.yml`, `cd.yml` (API), `cd-web.yml` (frontend)

## Notes / smaller follow-ups (non-blocking)

- The model `claude-sonnet-4-5` is marked **LEGACY** by AWS (still works). Consider
  bumping `bedrock_model_id` to an ACTIVE model later (one-line tfvars change).
- The API is **HTTP** (no custom domain/TLS on the ALB yet). For production, add an
  ACM cert + HTTPS listener and a custom domain. The frontend is already HTTPS via
  CloudFront.
- CRM/ERP/e-sign integrations remain future Secrets Manager placeholders, as planned.
