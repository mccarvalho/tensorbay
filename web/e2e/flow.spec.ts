import { test } from '@playwright/test';
import type { Page } from '@playwright/test';

const BASE = process.env.E2E_BASE_URL ?? 'https://d22xy9yyfwju3n.cloudfront.net';

function wire(page: Page, tag: string) {
  page.on('console', (m) => {
    if (m.type() === 'error') console.log(`[${tag}] CONSOLE: ${m.text()}`);
  });
  page.on('pageerror', (e) => console.log(`[${tag}] PAGEERR: ${e.message}`));
  page.on('response', async (resp) => {
    const url = resp.url();
    const ct = resp.headers()['content-type'] ?? '';
    if (url.includes('/v1/') || url.includes('/oauth2/') || url.endsWith('/token')) {
      console.log(`[${tag}] RESP ${resp.status()} ${ct.split(';')[0]} ${url.slice(0, 90)}`);
    }
  });
}

test('fresh visitor (no session) — what renders and what is fetched', async ({ page }) => {
  wire(page, 'fresh');
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(1500);
  const url = page.url();
  const bodyText = (await page.locator('body').innerText()).slice(0, 300);
  console.log('\n[fresh] landed URL:', url);
  console.log('[fresh] visible text:', JSON.stringify(bodyText));
});

test('callback with a bogus code — reproduce the token-exchange path', async ({ page }) => {
  wire(page, 'cb');
  await page.goto(`${BASE}/callback?code=BOGUS_TEST_CODE`, {
    waitUntil: 'networkidle',
    timeout: 30000,
  });
  await page.waitForTimeout(2000);
  const bodyText = (await page.locator('body').innerText()).slice(0, 400);
  console.log('\n[cb] visible text:', JSON.stringify(bodyText));
});
