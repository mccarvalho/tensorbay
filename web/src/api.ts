import { config } from './config';
import { getSession, refresh, clearSession } from './auth';

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(
  method: string,
  path: string,
  payload?: unknown,
  retried = false,
): Promise<T> {
  // Once a session-expiry redirect is underway, fail fast — don't pile on.
  if (redirecting) {
    throw new ApiError(401, 'Session expired', null);
  }
  const session = getSession();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (session?.accessToken) {
    headers.Authorization = `Bearer ${session.accessToken}`;
  }

  const resp = await fetch(`${config.apiBaseUrl}${path}`, {
    method,
    headers,
    body: payload !== undefined ? JSON.stringify(payload) : undefined,
    // Never read API responses from the browser HTTP cache. Prevents a stale
    // cached 200/HTML (from an earlier broken deploy) from being replayed.
    cache: 'no-store',
  });

  // Auto-refresh once on 401, then retry. Single-flight so concurrent 401s
  // don't each trigger a redirect storm.
  if (resp.status === 401 && !retried) {
    const ok = await refreshOnce();
    if (ok) return request<T>(method, path, payload, true);
    clearAndRedirect();
    throw new ApiError(401, 'Session expired', null);
  }

  const text = await resp.text();
  // Defensive parse: a stray HTML body (e.g. an SPA shell served by a proxy or a
  // stale service worker) must NOT blow up with "Unexpected token '<'".
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      throw new ApiError(
        resp.status || 502,
        'Unexpected non-JSON response from the API. Please hard-refresh.',
        text.slice(0, 200),
      );
    }
  }
  if (!resp.ok) {
    const detail =
      body && typeof body === 'object' && 'detail' in body
        ? JSON.stringify((body as { detail: unknown }).detail)
        : resp.statusText;
    throw new ApiError(resp.status, detail, body);
  }
  return body as T;
}

// --- single-flight refresh + clean logout --------------------------------- //
let refreshInFlight: Promise<boolean> | null = null;

function refreshOnce(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = refresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

let redirecting = false;
function clearAndRedirect(): void {
  if (redirecting) return;
  redirecting = true;
  clearSession();
  // Same-origin hard redirect to the login screen — instant and loop-proof.
  // (Full Cognito logout is still available via the Logout button.)
  window.location.assign('/login');
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, payload?: unknown) => request<T>('POST', path, payload),
  put: <T>(path: string, payload?: unknown) => request<T>('PUT', path, payload),
  patch: <T>(path: string, payload?: unknown) => request<T>('PATCH', path, payload),
  del: <T>(path: string) => request<T>('DELETE', path),
};
