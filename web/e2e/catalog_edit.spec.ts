import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const BASE = process.env.E2E_BASE_URL ?? 'https://d22xy9yyfwju3n.cloudfront.net';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));
const stamp = Date.now().toString().slice(-6);
test('catalog SKU edit + delete via UI', async ({ page }) => {
  const s = { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now()+3600_000 };
  await page.addInitScript((sess) => { localStorage.setItem('neocloud.session', JSON.stringify(sess)); }, s);
  page.on('dialog', (d) => d.accept());  // auto-accept the delete confirm()
  const bad: string[] = [];
  page.on('response', (r) => { const u=r.url(); if(u.includes('/v1/') && (r.headers()['content-type']??'').includes('html')) bad.push('HTML '+u); });
  page.on('pageerror', (e) => bad.push('PAGEERR ' + e.message));

  await page.goto(`${BASE}/catalog`, { waitUntil: 'networkidle', timeout: 30000 });
  const code = `EDIT-TEST-${stamp}`;

  // create
  await page.getByRole('button', { name: '+ New SKU' }).click();
  await page.locator('#s_code').fill(code);
  await page.locator('#s_name').fill('Original Name');
  await page.getByRole('button', { name: 'Create SKU' }).click();
  await expect(page.getByText(code)).toBeVisible({ timeout: 10000 });

  // edit — change the name
  await page.getByRole('row', { name: new RegExp(code) }).getByRole('button', { name: 'Edit' }).click();
  await expect(page.getByRole('heading', { name: 'Edit SKU' })).toBeVisible();
  await page.locator('#s_name').fill('Edited Name');
  await page.getByRole('button', { name: 'Save Changes' }).click();
  await expect(page.getByText('Edited Name')).toBeVisible({ timeout: 10000 });

  // delete
  await page.getByRole('row', { name: new RegExp(code) }).getByRole('button', { name: 'Delete' }).click();
  await expect(page.getByText(code)).toHaveCount(0, { timeout: 10000 });

  console.log('[catedit] problems:', bad.length ? bad.join(' | ') : 'NONE');
  expect(bad).toEqual([]);
});
