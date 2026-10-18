// Runtime configuration.
// In dev, Vite proxies / defaults point at the live AWS resources so the app
// works out-of-the-box. In production these are injected at build time via
// VITE_* env vars (see .env.example and the CI workflow).

export const config = {
  // Deployment environment ("dev" | "prod"). Set explicitly via VITE_ENVIRONMENT
  // at build time; otherwise inferred from the Cognito domain (prod builds point
  // at neocloud-prod-auth). Defaults to "dev" so the non-prod banner shows unless
  // we're confidently in prod.
  environment:
    (import.meta.env.VITE_ENVIRONMENT as string | undefined) ??
    ((import.meta.env.VITE_COGNITO_DOMAIN ?? '').includes('prod') ? 'prod' : 'dev'),

  // Same-origin by default: the SPA is served by CloudFront, which also proxies
  // /v1/*, /health, /docs to the ALB. This keeps every request same-origin HTTPS
  // (no mixed-content, no CORS). Override with VITE_API_BASE_URL for local dev
  // against the raw ALB if needed.
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? '',

  // Cognito hosted UI (OAuth2 authorization-code flow)
  cognito: {
    domain:
      import.meta.env.VITE_COGNITO_DOMAIN ??
      'https://neocloud-dev-auth.auth.us-east-2.amazoncognito.com',
    clientId:
      import.meta.env.VITE_COGNITO_CLIENT_ID ?? '69ua89fisqeohfmcdhc6a7d16',
    // Where Cognito returns the auth code. Must be registered as a callback URL.
    redirectUri:
      import.meta.env.VITE_COGNITO_REDIRECT_URI ??
      `${window.location.origin}/callback`,
    logoutUri:
      import.meta.env.VITE_COGNITO_LOGOUT_URI ??
      `${window.location.origin}/`,
    scope: 'openid email profile',
    // Identity provider to short-circuit straight to Google, or undefined to
    // show the hosted-UI chooser (Google + native Cognito).
    googleIdp: 'Google',
  },

  // Feature flags
  features: {
    // AI document generation requires the Anthropic "use case details" form to
    // be submitted in the Bedrock console (us-east-2). Until then the generate
    // endpoint returns 500, so the UI hides the generator. Flip to true (or set
    // VITE_AI_DOCS=1) once model access is enabled.
    aiDocs: (import.meta.env.VITE_AI_DOCS ?? '') === '1',
  },
} as const;
