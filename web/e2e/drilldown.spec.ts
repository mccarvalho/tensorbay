import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const BASE = 'https://d22xy9yyfwju3n.cloudfront.net';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));
const S = '72103', CUST = 'a8471c7c-e18d-4c1b-869f-252c4bff0f6f', CTR = 'aa11ed69-e2f4-4c7f-83fe-dde622357104', OPP = '699432f1-b618-41e7-87d4-aed744e350eb';

test('entity drill-down navigation', async ({ page }) => {
  const sess = { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now()+3600_000 };
  await page.addInitScript((x) => { localStorage.setItem('neocloud.session', JSON.stringify(x)); }, sess);
  const bad: string[] = [];
  page.on('response', (r) => { const u=r.url(); if(u.includes('/v1/')){ if(r.status()>=500) bad.push(r.status()+' '+u); if((r.headers()['content-type']??'').includes('html')) bad.push('HTML '+u);} });
  page.on('pageerror', (e) => bad.push('PAGEERR ' + e.message));

  // Customer detail -> related records render
  await page.goto(BASE + '/customers/' + CUST, { waitUntil: 'networkidle', timeout: 30000 });
  await expect(page.getByText('Drill Co ' + S).first()).toBeVisible();
  await expect(page.getByText('CONTRACTS', { exact: true })).toBeVisible();
  await expect(page.getByText('OPPORTUNITIES', { exact: true })).toBeVisible();
  await expect(page.getByText('RESERVATIONS', { exact: true })).toBeVisible();
  await expect(page.getByText('DRILL-' + S)).toBeVisible({ timeout: 10000 });

  // ContractDetail direct
  await page.goto(BASE + '/contracts/' + CTR, { waitUntil: 'networkidle' });
  await expect(page.getByRole('heading', { name: 'DRILL-' + S })).toBeVisible({ timeout: 10000 });
  await expect(page.getByText('LINE ITEMS', { exact: true })).toBeVisible();
  await expect(page.getByText('RESERVATIONS', { exact: true }).first()).toBeVisible();
  // the seeded reservation (16 H200) shows in the contract's reservations
  await expect(page.getByText('16').first()).toBeVisible({ timeout: 10000 });

  // OpportunityDetail direct
  await page.goto(BASE + '/opportunities/' + OPP, { waitUntil: 'networkidle' });
  await expect(page.getByRole('heading', { name: '32× H200' })).toBeVisible({ timeout: 10000 });
  await expect(page.getByText('QUOTES', { exact: true })).toBeVisible();
  await expect(page.getByText('Drill Co ' + S).first()).toBeVisible();

  console.log('[drill] problems:', bad.length ? bad.join(' | ') : 'NONE');
  expect(bad).toEqual([]);
});
