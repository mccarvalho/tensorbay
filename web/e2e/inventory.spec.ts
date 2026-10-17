import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const BASE = process.env.E2E_BASE_URL ?? 'https://d22xy9yyfwju3n.cloudfront.net';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));
const s6 = Date.now().toString().slice(-6);

test('inventory full chain + capacity incoming via UI', async ({ page }) => {
  const sess = { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now()+3600_000 };
  await page.addInitScript((x) => { localStorage.setItem('neocloud.session', JSON.stringify(x)); }, sess);
  page.on('dialog', (d) => d.accept());
  const bad: string[] = [];
  page.on('response', (r) => { const u=r.url(); if(u.includes('/v1/') && (r.headers()['content-type']??'').includes('html')) bad.push('HTML '+u); });
  page.on('pageerror', (e) => bad.push('PAGEERR ' + e.message));

  await page.goto(`${BASE}/inventory`, { waitUntil: 'networkidle', timeout: 30000 });
  await expect(page.getByRole('heading', { name: 'Inventory' })).toBeVisible();

  // helper to create a simple code/name entity on the current tab
  async function createRegion() {
    await page.getByRole('button', { name: '+ New Region' }).click();
    await page.locator('input.input').first().fill(`rg-${s6}`);
    await page.locator('input.input').nth(1).fill('E2E Region');
    await page.getByRole('button', { name: 'Create Region' }).click();
    await expect(page.getByText(`rg-${s6}`)).toBeVisible({ timeout: 10000 });
  }
  await createRegion();

  // Datacenter (parent picker = region)
  await page.getByRole('button', { name: 'Datacenters' }).click();
  await page.getByRole('button', { name: '+ New Datacenter' }).click();
  await page.locator('select.input').first().selectOption({ label: `rg-${s6} — E2E Region` });
  await page.getByLabel('Code').fill(`dc-${s6}`);
  await page.getByLabel('Name').fill('E2E DC');
  await page.getByRole('button', { name: 'Create Datacenter' }).click();
  await expect(page.getByText(`dc-${s6}`)).toBeVisible({ timeout: 10000 });

  // Cluster
  await page.getByRole('button', { name: 'Clusters' }).click();
  await page.getByRole('button', { name: '+ New Cluster' }).click();
  await page.locator('select.input').first().selectOption({ label: `dc-${s6} — E2E DC` });
  await page.getByLabel('Code').fill(`cl-${s6}`);
  await page.getByLabel('GPU Model').fill('H200');
  await page.getByLabel('Name').fill('E2E Cluster');
  await page.getByRole('button', { name: 'Create Cluster' }).click();
  await expect(page.getByText(`cl-${s6}`)).toBeVisible({ timeout: 10000 });

  // Rack
  await page.getByRole('button', { name: 'Racks' }).click();
  await page.getByRole('button', { name: '+ New Rack' }).click();
  await page.locator('select.input').first().selectOption({ label: `cl-${s6} — E2E Cluster` });
  await page.getByLabel('Code').fill(`rk-${s6}`);
  await page.getByRole('button', { name: 'Create Rack' }).click();
  await expect(page.getByText(`rk-${s6}`)).toBeVisible({ timeout: 10000 });

  // Server
  await page.getByRole('button', { name: 'Servers' }).click();
  await page.getByRole('button', { name: '+ New Server' }).click();
  await page.locator('select.input').first().selectOption({ label: `rk-${s6}` });
  await page.getByLabel('Code').fill(`sv-${s6}`);
  await page.getByRole('button', { name: 'Create Server' }).click();
  await expect(page.getByText(`sv-${s6}`)).toBeVisible({ timeout: 10000 });

  // GPU asset (full fields)
  await page.getByRole('button', { name: 'GPUs' }).click();
  await page.getByRole('button', { name: '+ New GPU' }).click();
  await page.locator('select.input').first().selectOption({ label: `sv-${s6}` });
  await page.getByLabel('GPU ID').fill(`gpu-${s6}`);
  await page.getByLabel('Memory (GB)').fill('141');
  await page.getByRole('button', { name: 'Create GPU' }).click();
  await expect(page.getByText(`gpu-${s6}`)).toBeVisible({ timeout: 10000 });

  // Capacity incoming CRUD
  await page.goto(`${BASE}/capacity`, { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: '+ New Incoming' }).click();
  await page.locator('#inc_model').fill('B300');
  await page.locator('#inc_qty').fill('512');
  await page.locator('#inc_po').fill(`PO-${s6}`);
  await page.getByRole('button', { name: 'Create Incoming' }).click();
  await expect(page.getByText(`PO-${s6}`)).toBeVisible({ timeout: 10000 });

  console.log('[inv] problems:', bad.length ? bad.join(' | ') : 'NONE');
  expect(bad).toEqual([]);
});
