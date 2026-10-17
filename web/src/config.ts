// Runtime configuration.
// In dev, Vite proxies / defaults point at the live AWS resources so the app
// works out-of-the-box. In production these are injected at build time via
// VITE_* env vars (see .env.example and the CI workflow).

export const config = {
  apiBaseUrl:
    import.meta.env.VITE_API_BASE_URL ??
    'http://neocloud-dev-alb-1924778288.us-east-2.elb.amazonaws.com',

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
} as const;
