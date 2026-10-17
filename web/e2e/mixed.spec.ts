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
}

// Simulate the OLD broken bundle: valid session, but the app tries to call the
// HTTP ALB directly (mixed content). We emulate by intercepting the app's fetch
// to /v1/* and redirecting to the http ALB, observing what the browser does.
test('mixed-content HTTP ALB call from an HTTPS page', async ({ page }) => {
  wire(page, 'mixed');
  const session = {
    accessToken: tokens.access,
    idToken: tokens.id,
    refreshToken: tokens.refresh,
    expiresAt: Date.now() + 3600_000,
  };
  await page.addInitScript((s) => {
    window.localStorage.setItem('neocloud.session', JSON.stringify(s));
    // Monkeypatch fetch to rewrite same-origin /v1 calls to the http ALB,
    // reproducing the old bundle's behavior.
    const orig = window.fetch.bind(window);
    // @ts-expect-error test shim
    window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
      let url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/v1/')) {
        url = url.replace(
          /^https:\/\/[^/]+/,
          'http://neocloud-dev-alb-1924778288.us-east-2.elb.amazonaws.com',
        );
      }
      return orig(url, init);
    };
  }, session);
  await page.goto(`${BASE}/customers`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2500);
  const body = (await page.locator('body').innerText()).slice(0, 400);
  console.log('[mixed] body:', JSON.stringify(body));
});
