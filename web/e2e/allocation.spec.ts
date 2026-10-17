import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const BASE = 'https://d22xy9yyfwju3n.cloudfront.net';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));
const S = '71407';

test('reservation -> allocation -> edit -> release', async ({ page }) => {
  const sess = { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now()+3600_000 };
  await page.addInitScript((x) => { localStorage.setItem('neocloud.session', JSON.stringify(x)); }, sess);
  page.on('dialog', (d) => d.accept());
  const bad: string[] = [];
  page.on('response', (r) => { const u=r.url(); if(u.includes('/v1/')){ if(r.status()>=500) bad.push(r.status()+' '+u); if((r.headers()['content-type']??'').includes('html')) bad.push('HTML '+u);} });
  page.on('pageerror', (e) => bad.push('PAGEERR ' + e.message));

  await page.goto(BASE + '/reservations', { waitUntil: 'networkidle', timeout: 30000 });
  await expect(page.getByRole('heading', { name: /Reservations/ })).toBeVisible();

  // create reservation against the seeded customer/contract
  await page.getByRole('button', { name: '+ New Reservation' }).click();
  await page.locator('#res_customer').selectOption({ label: 'Alloc Co ' + S });
  await page.locator('#res_contract').selectOption({ label: 'ALLOC-' + S });
  await page.locator('#res_model').fill('H200');
  await page.locator('#res_qty').fill('4');
  await page.getByRole('button', { name: 'Create Reservation' }).click();
  await expect(page.getByRole('cell', { name: 'ALLOC-' + S })).toBeVisible({ timeout: 10000 });

  // open Allocations for that reservation's row
  const row = page.getByRole('row', { name: new RegExp('ALLOC-' + S) });
  await row.getByRole('button', { name: /Allocations/ }).click();
  await expect(page.getByRole('heading', { name: /Allocations ·/ })).toBeVisible();

  // allocate to the seeded cluster + pick the seeded GPU
  await page.getByRole('button', { name: '+ Allocate' }).click();
  await page.locator('#alloc_cluster').selectOption({ label: 'alcl-' + S + ' — Alloc Cluster' });
  await page.getByText('algpu-' + S).click(); // toggles the checkbox label
  await page.getByRole('button', { name: 'Allocate' }).click();
  // the new allocation row shows the cluster code + 1 GPU
  await expect(page.getByText('alcl-' + S).first()).toBeVisible({ timeout: 10000 });
  await expect(page.getByText('1 GPU').first()).toBeVisible({ timeout: 10000 });

  const dialog = page.getByRole('dialog');
  // edit its status -> ALLOCATED (scoped to the dialog so we don't hit the row's Edit)
  await dialog.getByRole('button', { name: 'Edit' }).first().click();
  await page.locator('#alloc_status').selectOption('ALLOCATED');
  await page.getByRole('button', { name: 'Save Changes' }).click();
  await expect(dialog.getByText('ALLOCATED').first()).toBeVisible({ timeout: 10000 });

  // release it
  await dialog.getByRole('button', { name: 'Release' }).first().click();
  await expect(dialog.getByText('RELEASED').first()).toBeVisible({ timeout: 10000 });

  console.log('[alloc] problems:', bad.length ? bad.join(' | ') : 'NONE');
  expect(bad).toEqual([]);
});
