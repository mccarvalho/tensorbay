// Cognito hosted-UI OAuth2 authorization-code flow with PKCE.
// No client secret is used (public SPA client), so PKCE protects the exchange.
import { config } from './config';

const STORAGE_KEY = 'neocloud.session';
const PKCE_VERIFIER_KEY = 'neocloud.pkce_verifier';

export interface Session {
  accessToken: string;
  idToken: string;
  refreshToken?: string;
  expiresAt: number; // epoch ms
}

export interface UserClaims {
  sub: string;
  email?: string;
  name?: string;
  groups: string[];
}

// ---------- PKCE helpers ----------
function base64UrlEncode(bytes: Uint8Array): string {
  let str = '';
  for (const b of bytes) str += String.fromCharCode(b);
  return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function sha256(input: string): Promise<Uint8Array> {
  const data = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return new Uint8Array(digest);
}

function randomString(len = 64): string {
  const bytes = new Uint8Array(len);
  crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
}

// ---------- session storage ----------
export function getSession(): Session | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const s = JSON.parse(raw) as Session;
    return s;
  } catch {
    return null;
  }
}

function setSession(s: Session): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
}

export function clearSession(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function isAuthenticated(): boolean {
  const s = getSession();
  return !!s && s.expiresAt > Date.now() + 5000;
}

// Decode a base64url JWT segment as proper UTF-8 (atob yields a Latin-1 binary
// string, which mangles multi-byte chars like "í" -> "Ã­").
function decodeJwtSegment(segment: string): Record<string, unknown> {
  const b64 = segment.replace(/-/g, '+').replace(/_/g, '/');
  const binary = atob(b64);
  const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
  const json = new TextDecoder('utf-8').decode(bytes);
  return JSON.parse(json);
}

export function decodeClaims(idToken: string): UserClaims {
  const payload = decodeJwtSegment(idToken.split('.')[1]);
  return {
    sub: payload.sub as string,
    email: payload.email as string | undefined,
    name: (payload.name as string | undefined) ?? (payload.email as string | undefined),
    groups: (payload['cognito:groups'] as string[] | undefined) ?? [],
  };
}

// ---------- flow ----------
export async function login(options?: { useGoogle?: boolean }): Promise<void> {
  const verifier = randomString(64);
  sessionStorage.setItem(PKCE_VERIFIER_KEY, verifier);
  const challenge = base64UrlEncode(await sha256(verifier));

  const params = new URLSearchParams({
    response_type: 'code',
    client_id: config.cognito.clientId,
    redirect_uri: config.cognito.redirectUri,
    scope: config.cognito.scope,
    code_challenge_method: 'S256',
    code_challenge: challenge,
  });
  if (options?.useGoogle) {
    params.set('identity_provider', config.cognito.googleIdp);
  }
  window.location.assign(
    `${config.cognito.domain}/oauth2/authorize?${params.toString()}`,
  );
}

export async function handleCallback(code: string): Promise<void> {
  const verifier = sessionStorage.getItem(PKCE_VERIFIER_KEY);
  if (!verifier) throw new Error('Missing PKCE verifier; restart login.');

  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: config.cognito.clientId,
    code,
    redirect_uri: config.cognito.redirectUri,
    code_verifier: verifier,
  });

  const resp = await fetch(`${config.cognito.domain}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });
  if (!resp.ok) {
    throw new Error(`Token exchange failed: ${resp.status} ${await resp.text()}`);
  }
  const tok = await resp.json();
  sessionStorage.removeItem(PKCE_VERIFIER_KEY);
  setSession({
    accessToken: tok.access_token,
    idToken: tok.id_token,
    refreshToken: tok.refresh_token,
    expiresAt: Date.now() + (tok.expires_in ?? 3600) * 1000,
  });
}

export async function refresh(): Promise<boolean> {
  const s = getSession();
  if (!s?.refreshToken) return false;
  const body = new URLSearchParams({
    grant_type: 'refresh_token',
    client_id: config.cognito.clientId,
    refresh_token: s.refreshToken,
  });
  const resp = await fetch(`${config.cognito.domain}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });
  if (!resp.ok) {
    clearSession();
    return false;
  }
  const tok = await resp.json();
  setSession({
    accessToken: tok.access_token,
    idToken: tok.id_token ?? s.idToken,
    refreshToken: tok.refresh_token ?? s.refreshToken,
    expiresAt: Date.now() + (tok.expires_in ?? 3600) * 1000,
  });
  return true;
}

export function logout(): void {
  clearSession();
  const params = new URLSearchParams({
    client_id: config.cognito.clientId,
    logout_uri: config.cognito.logoutUri,
  });
  window.location.assign(
    `${config.cognito.domain}/logout?${params.toString()}`,
  );
}
