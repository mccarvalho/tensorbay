import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const BASE = process.env.E2E_BASE_URL ?? 'https://d22xy9yyfwju3n.cloudfront.net';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));

test('capacity fleet overview + overselling + incoming timeline', async ({ page }) => {
  const sess = { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now()+3600_000 };
  await page.addInitScript((x) => { localStorage.setItem('neocloud.session', JSON.stringify(x)); }, sess);
  const bad: string[] = [];
  page.on('response', (r) => { const u=r.url(); if(u.includes('/v1/') && (r.headers()['content-type']??'').includes('html')) bad.push('HTML '+u); });
  page.on('pageerror', (e) => bad.push('PAGEERR ' + e.message));

  await page.goto(`${BASE}/capacity`, { waitUntil: 'networkidle', timeout: 30000 });
  await expect(page.getByRole('heading', { name: 'Capacity Planning' })).toBeVisible();

  // Fleet section headers
  await expect(page.getByText('FLEET · CAPACITY & OVERSELLING')).toBeVisible();
  await expect(page.getByText('INCOMING · TIMELINE')).toBeVisible();

  // Our seeded H200 should appear as a bar label; timeline should show +GPUs
  await expect(page.getByText('physical', { exact: false }).first()).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/\+\s*[\d,]+ GPUs/).first()).toBeVisible({ timeout: 15000 });

  console.log('[cap] problems:', bad.length ? bad.join(' | ') : 'NONE');
  expect(bad).toEqual([]);
});
