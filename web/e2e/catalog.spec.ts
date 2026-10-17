import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const BASE = process.env.E2E_BASE_URL ?? 'https://d22xy9yyfwju3n.cloudfront.net';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));
const stamp = Date.now().toString().slice(-6);
test('catalog: create SKU + price book + price via UI', async ({ page }) => {
  const s = { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now()+3600_000 };
  await page.addInitScript((sess) => { localStorage.setItem('neocloud.session', JSON.stringify(sess)); }, s);
  const bad: string[] = [];
  page.on('response', (r) => { const u=r.url(); if(u.includes('/v1/') && (r.headers()['content-type']??'').includes('html')) bad.push('HTML '+u); });
  page.on('pageerror', (e) => bad.push('PAGEERR ' + e.message));

  await page.goto(`${BASE}/catalog`, { waitUntil: 'networkidle', timeout: 30000 });
  await expect(page.getByRole('heading', { name: 'Product Catalog & Pricing' })).toBeVisible();

  // --- SKU ---
  await page.getByRole('button', { name: '+ New SKU' }).click();
  const code = `GPU-H200-E2E-${stamp}`;
  await page.locator('#s_code').fill(code);
  await page.locator('#s_name').fill('E2E H200 SKU');
  await page.getByRole('button', { name: 'Create SKU' }).click();
  await expect(page.getByText(code)).toBeVisible({ timeout: 10000 });

  // --- Price Book ---
  await page.getByRole('button', { name: 'Price Books' }).click();
  await page.getByRole('button', { name: '+ New Price Book' }).click();
  const book = `E2E List ${stamp}`;
  await page.locator('#b_name').fill(book);
  await page.getByRole('button', { name: 'Create Price Book' }).click();
  await expect(page.getByText(book)).toBeVisible({ timeout: 10000 });

  // --- Price (maps the SKU + book) ---
  await page.getByRole('button', { name: 'Prices', exact: true }).click();
  await page.getByRole('button', { name: '+ New Price' }).click();
  await page.locator('#p_sku').selectOption({ label: `${code} — E2E H200 SKU` });
  await page.locator('#p_book').selectOption({ label: `${book} (LIST)` });
  await page.locator('#p_price').fill('3.10');
  await page.getByRole('button', { name: 'Create Price', exact: true }).click();
  await expect(page.getByText(code).first()).toBeVisible({ timeout: 10000 });
  await expect(page.getByText('$3.10').first()).toBeVisible();

  console.log('[catalog] problems:', bad.length ? bad.join(' | ') : 'NONE');
  expect(bad).toEqual([]);
});
