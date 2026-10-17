# NeoCloud Web — TensorBay GPU Control Plane (frontend)

React + Vite + TypeScript single-page app for the NeoCloud Platform, styled with
the **TensorBay brand** (deep-purple dark theme, cyan/purple accents) drawn from
the Commission Plan deck and the official logo from tensorbay.io.

**Live:** https://d22xy9yyfwju3n.cloudfront.net (CloudFront + S3, `us-east-2`)

## Stack

- React 18 + Vite 5 + TypeScript (strict)
- Tailwind CSS 3 (brand tokens in `tailwind.config.js`)
- react-router-dom v6 (SPA routing)
- @tanstack/react-query v5 (data fetching/caching)
- Cognito hosted-UI OAuth2 **authorization-code flow with PKCE** (no client secret)

## Brand

Palette extracted from the TensorBay Commission Plan deck:

| Token | Hex | Use |
|-------|-----|-----|
| `space` | `#0D0221` | deep-space background |
| `space-600` | `#241043` | card/panel surface |
| `cyan` | `#00D4FF` | primary accent, section eyebrows |
| `grape` | `#B165FB` | secondary accent |
| `grape-soft` | `#B9A9D6` | muted body text |
| `flamingo` | `#FF6EC4` | tertiary accent / gradients |

Logo + symbol (`public/brand/*.webp`) are the official assets from tensorbay.io.

## Project layout

```
web/
├── public/brand/        # TensorBay logo + symbol (webp)
├── src/
│   ├── config.ts        # runtime config (API base, Cognito) from VITE_* env
│   ├── auth.ts          # PKCE OAuth: login/handleCallback/refresh/logout
│   ├── api.ts           # fetch client: bearer token + auto-refresh on 401
│   ├── index.css        # Tailwind + brand component classes
│   ├── components/      # AppLayout, RequireAuth, ui.tsx (KpiCard, DataTable, …)
│   └── pages/           # Login, Callback, Dashboard, Customers, Contracts,
│                        #   Inventory, Capacity, Reservations, Documents
├── openapi.snapshot.json # API contract snapshot (the 58-path live spec)
└── ...config files
```

## Run locally

```bash
cd web
npm install
npm run dev          # http://localhost:3000  (uses live ALB API + Cognito by default)
```

`http://localhost:3000/callback` and `http://localhost:3000/` are registered as
Cognito callback/logout URLs, so SSO works in local dev too.

## Build

```bash
npm run build        # tsc --noEmit + vite build  ->  dist/
npm run preview      # serve the production build locally
```

## Configuration (env vars, all optional — sensible defaults point at dev)

| Var | Default |
|-----|---------|
| `VITE_API_BASE_URL` | live ALB |
| `VITE_COGNITO_DOMAIN` | `https://neocloud-dev-auth.auth.us-east-2.amazoncognito.com` |
| `VITE_COGNITO_CLIENT_ID` | the dev app client |
| `VITE_COGNITO_REDIRECT_URI` | `${origin}/callback` |
| `VITE_COGNITO_LOGOUT_URI` | `${origin}/` |

## Deploy

Automatic via GitHub Actions: pushing changes under `web/**` to `main` triggers
`.github/workflows/cd-web.yml`, which builds, syncs to S3, and invalidates
CloudFront (keyless, via the OIDC deploy role).

Manual:

```bash
npm run build
aws s3 sync dist/ s3://neocloud-dev-web/ --delete --region us-east-2
aws cloudfront create-invalidation --distribution-id E2EL9X8Q231YLE --paths "/*"
```

## Auth flow

1. `/login` → `login({useGoogle:true})` redirects to the Cognito hosted UI, which
   federates to Google Workspace.
2. Google returns to Cognito; Cognito redirects to `/callback?code=…`.
3. `/callback` exchanges the code (PKCE) for tokens, stores the session, and
   routes to the dashboard.
4. `src/api.ts` attaches the access token to every `/v1/*` request and silently
   refreshes on a 401.
