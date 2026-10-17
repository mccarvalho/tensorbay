import { test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { readFileSync } from 'node:fs';

const BASE = process.env.E2E_BASE_URL ?? 'https://d22xy9yyfwju3n.cloudfront.net';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));

function wire(page: Page, tag: string) {
  page.on('console', (m) => {
    if (m.type() === 'error') console.log(`[${tag}] CONSOLE: ${m.text()}`);
  });
  page.on('pageerror', (e) => console.log(`[${tag}] PAGEERR: ${e.message}`));
  page.on('response', async (resp) => {
    const url = resp.url();
    const ct = resp.headers()['content-type'] ?? '';
    if (url.includes('/v1/') || url.includes('/oauth2/') || url.endsWith('/token')) {
      console.log(`[${tag}] RESP ${resp.status()} ${ct.split(';')[0]} ${url.slice(0, 95)}`);
    }
  });
}

// Scenario A: a stored session whose accessToken is a garbage/expired string but
// expiresAt is still in the future (so isAuthenticated() passes and the app calls
// the API, gets 401, then tries to refresh).
test('stale/invalid access token triggers refresh path', async ({ page }) => {
  wire(page, 'stale');
  const badSession = {
    accessToken: 'invalid.garbage.token',
    idToken: tokens.id,
    refreshToken: 'invalid-refresh',
    expiresAt: Date.now() + 3600_000,
  };
  await page.addInitScript((s) => {
    window.localStorage.setItem('neocloud.session', JSON.stringify(s));
  }, badSession);
  await page.goto(`${BASE}/customers`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2500);
  const body = (await page.locator('body').innerText()).slice(0, 300);
  console.log('[stale] body:', JSON.stringify(body));
  console.log('[stale] url:', page.url());
});

// Scenario B: session where expiresAt is already past (isAuthenticated() false) but
// present — RequireAuth should redirect to /login cleanly.
test('expired session redirects to login', async ({ page }) => {
  wire(page, 'expired');
  const expired = {
    accessToken: tokens.access,
    idToken: tokens.id,
    refreshToken: tokens.refresh,
    expiresAt: Date.now() - 1000,
  };
  await page.addInitScript((s) => {
    window.localStorage.setItem('neocloud.session', JSON.stringify(s));
  }, expired);
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(1500);
  console.log('[expired] url:', page.url());
});
