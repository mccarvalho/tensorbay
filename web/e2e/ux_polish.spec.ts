import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const BASE = 'https://d22xy9yyfwju3n.cloudfront.net';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));
const S = Date.now().toString().slice(-6);

test('customers: create+toast, search, edit+toast, delete+toast', async ({ page }) => {
  const sess = { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now()+3600_000 };
  await page.addInitScript((x) => { localStorage.setItem('neocloud.session', JSON.stringify(x)); }, sess);
  page.on('dialog', (d) => d.accept());
  const bad: string[] = [];
  page.on('response', (r) => { const u=r.url(); if(u.includes('/v1/')){ if(r.status()>=500) bad.push(r.status()+' '+u); if((r.headers()['content-type']??'').includes('html')) bad.push('HTML '+u);} });
  page.on('pageerror', (e) => bad.push('PAGEERR ' + e.message));

  await page.goto(BASE + '/customers', { waitUntil: 'networkidle', timeout: 30000 });
  await expect(page.getByRole('heading', { name: 'Customers' })).toBeVisible();

  // create -> success toast
  await page.getByRole('button', { name: '+ New Customer' }).click();
  await page.locator('#legal_name').fill('UX Polish Co ' + S);
  await page.getByRole('button', { name: 'Create Customer' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Customer created' })).toBeVisible({ timeout: 10000 });

  // search narrows to our row
  await page.getByPlaceholder(/Search by name/).fill('UX Polish Co ' + S);
  await expect(page.getByRole('cell', { name: 'UX Polish Co ' + S })).toBeVisible();

  // edit -> change status to ACTIVE -> success toast
  const row = page.getByRole('row', { name: new RegExp('UX Polish Co ' + S) });
  await row.getByRole('button', { name: 'Edit' }).click();
  await page.locator('#cust_status').selectOption('ACTIVE');
  await page.getByRole('button', { name: 'Save Changes' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Customer updated' })).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole('row', { name: new RegExp('UX Polish Co ' + S) }).getByText('ACTIVE')).toBeVisible();

  // delete -> success toast
  await page.getByRole('row', { name: new RegExp('UX Polish Co ' + S) }).getByRole('button', { name: 'Delete' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Customer deleted' })).toBeVisible({ timeout: 10000 });

  console.log('[ux] problems:', bad.length ? bad.join(' | ') : 'NONE');
  expect(bad).toEqual([]);
});
