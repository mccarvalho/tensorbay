import { config } from './config';
import { getSession, refresh, logout } from './auth';

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
  const session = getSession();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (session?.accessToken) {
    headers.Authorization = `Bearer ${session.accessToken}`;
  }

  const resp = await fetch(`${config.apiBaseUrl}${path}`, {
    method,
    headers,
    body: payload !== undefined ? JSON.stringify(payload) : undefined,
  });

  // Auto-refresh once on 401, then retry.
  if (resp.status === 401 && !retried) {
    const ok = await refresh();
    if (ok) return request<T>(method, path, payload, true);
    logout();
    throw new ApiError(401, 'Session expired', null);
  }

  const text = await resp.text();
  const body = text ? JSON.parse(text) : null;
  if (!resp.ok) {
    const detail =
      body && typeof body === 'object' && 'detail' in body
        ? JSON.stringify((body as { detail: unknown }).detail)
        : resp.statusText;
    throw new ApiError(resp.status, detail, body);
  }
  return body as T;
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, payload?: unknown) => request<T>('POST', path, payload),
  patch: <T>(path: string, payload?: unknown) => request<T>('PATCH', path, payload),
  del: <T>(path: string) => request<T>('DELETE', path),
};
