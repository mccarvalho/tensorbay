import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const BASE = process.env.E2E_BASE_URL ?? 'https://d22xy9yyfwju3n.cloudfront.net';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));

test('executive dashboard renders KPIs + charts', async ({ page }) => {
  const sess = { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now()+3600_000 };
  await page.addInitScript((x) => { localStorage.setItem('neocloud.session', JSON.stringify(x)); }, sess);
  const bad: string[] = [];
  page.on('response', (r) => { const u=r.url(); if(u.includes('/v1/') && (r.headers()['content-type']??'').includes('html')) bad.push('HTML '+u); });
  page.on('pageerror', (e) => bad.push('PAGEERR ' + e.message));

  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await expect(page.getByRole('heading', { name: 'Executive Control Plane' })).toBeVisible();

  // chart card titles
  await expect(page.getByText('Revenue Composition')).toBeVisible();
  await expect(page.getByText('Fleet Status Mix')).toBeVisible();
  await expect(page.getByText('GPU Demand vs Commitments')).toBeVisible();
  // KPI
  await expect(page.getByText('Installed GPUs')).toBeVisible();
  // recharts injects <svg class="recharts-surface"> once data renders
  await expect(page.locator('svg.recharts-surface').first()).toBeVisible({ timeout: 15000 });
  const svgCount = await page.locator('svg.recharts-surface').count();
  console.log('[dash] recharts svgs:', svgCount, '| problems:', bad.length ? bad.join(' | ') : 'NONE');
  expect(svgCount).toBeGreaterThanOrEqual(3);
  expect(bad).toEqual([]);

  await page.setViewportSize({ width: 1280, height: 1800 });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: '/tmp/dashboard.png', fullPage: true });
});
