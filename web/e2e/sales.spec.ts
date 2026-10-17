import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const BASE = process.env.E2E_BASE_URL ?? 'https://d22xy9yyfwju3n.cloudfront.net';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));
test('sales pipeline page loads with JSON and renders', async ({ page }) => {
  const s = { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now()+3600_000 };
  await page.addInitScript((sess) => { localStorage.setItem('neocloud.session', JSON.stringify(sess)); }, s);
  const bad: string[] = [];
  const seen: string[] = [];
  page.on('response', async (r) => {
    const u = r.url();
    if (!u.includes('/v1/')) return;
    const ct = r.headers()['content-type'] ?? '';
    seen.push(`${r.status()} ${ct.split(';')[0]} ${u.replace(BASE,'')}`);
    if (ct.includes('html')) bad.push(u);
  });
  page.on('pageerror', (e) => bad.push('PAGEERR ' + e.message));

  await page.goto(`${BASE}/sales`, { waitUntil: 'networkidle', timeout: 30000 });
  await expect(page.getByRole('heading', { name: 'Sales Pipeline' })).toBeVisible();
  await expect(page.getByText('Open Opportunities')).toBeVisible();
  await expect(page.getByText('Pipeline GPU Demand')).toBeVisible();

  // open the New Opportunity modal -> triggers customers fetch + shows capacity-check panel
  await page.getByRole('button', { name: '+ New Opportunity' }).click();
  await expect(page.getByText('Capacity Check')).toBeVisible();
  // run a capacity check (fires /v1/capacity/check)
  await page.getByRole('button', { name: /Check/ }).click();
  await page.waitForTimeout(1500);

  console.log('[sales] /v1 responses:');
  for (const line of [...new Set(seen)]) console.log('  ' + line);
  console.log('[sales] problems:', bad.length ? bad.join(' | ') : 'NONE');
  expect(bad, 'no HTML responses or page errors').toEqual([]);
});
