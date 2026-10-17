import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const BASE = 'https://d22xy9yyfwju3n.cloudfront.net';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));

test('account-owner autocomplete + persistence', async ({ page }) => {
  const sess = { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now()+3600_000 };
  await page.addInitScript((x) => { localStorage.setItem('neocloud.session', JSON.stringify(x)); }, sess);
  const bad: string[] = [];
  page.on('response', (r) => { const u=r.url(); if(u.includes('/v1/')){ if(r.status()>=500) bad.push(`${r.status()} ${u}`); if((r.headers()['content-type']??'').includes('html')) bad.push('HTML '+u);} });
  page.on('pageerror', (e) => bad.push('PAGEERR ' + e.message));

  await page.goto(`${BASE}/sales`, { waitUntil: 'networkidle', timeout: 30000 });
  await expect(page.getByRole('heading', { name: 'Sales Pipeline' })).toBeVisible();

  // open New Opportunity
  await page.getByRole('button', { name: /New Opportunity/i }).first().click();
  const owner = page.locator('#opp_owner');
  await expect(owner).toBeVisible();

  // type a fragment to trigger the directory dropdown, then pick Lizi
  await owner.click();
  await owner.fill('li');
  // dropdown option with Lizi should appear
  const option = page.getByRole('button', { name: /Lizi Santucci/ });
  await expect(option).toBeVisible({ timeout: 10000 });
  await option.click();
  // verified email badge appears
  await expect(page.getByText(/✓\s*lizi@tensorbay\.io/)).toBeVisible({ timeout: 5000 });
  await expect(owner).toHaveValue('Lizi Santucci');

  // fill the rest of the opp form and create
  // pick first customer
  const custSel = page.locator('select').first();
  await custSel.selectOption({ index: 1 });
  await page.getByRole('button', { name: /^Create Opportunity$/ }).click();

  // the new opp row should show the owner name
  await expect(page.getByText('Lizi Santucci').first()).toBeVisible({ timeout: 10000 });

  console.log('[owner] problems:', bad.length ? bad.join(' | ') : 'NONE');
  expect(bad).toEqual([]);
});
