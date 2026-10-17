import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const BASE = process.env.E2E_BASE_URL ?? 'https://d22xy9yyfwju3n.cloudfront.net';
const CID = '931188ca-d72a-4c96-8bf6-72ea4a1e0250';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));
test('CRM detail: contacts + activity timeline + log activity', async ({ page }) => {
  const s = { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now()+3600_000 };
  await page.addInitScript((sess) => { localStorage.setItem('neocloud.session', JSON.stringify(sess)); }, s);
  const bad: string[] = [];
  page.on('response', (r) => {
    const u = r.url(); if (!u.includes('/v1/')) return;
    const ct = r.headers()['content-type'] ?? '';
    if (ct.includes('html')) bad.push(`HTML ${u}`);
  });
  page.on('pageerror', (e) => bad.push('PAGEERR ' + e.message));

  await page.goto(`${BASE}/customers/${CID}`, { waitUntil: 'networkidle', timeout: 30000 });
  await expect(page.getByRole('heading', { name: 'CRM Test Co' })).toBeVisible();
  await expect(page.getByText('Contacts')).toBeVisible();
  await expect(page.getByText('Jane Buyer')).toBeVisible();              // seeded contact
  await expect(page.getByText('Activity Timeline')).toBeVisible();
  await expect(page.getByText('Intro call — H200 demand')).toBeVisible();// seeded activity
  await expect(page.getByText('Next follow-up')).toBeVisible();          // follow-up banner

  // log a new activity through the UI
  await page.getByRole('button', { name: '+ Log Activity' }).click();
  await page.locator('#a_subject').fill('E2E follow-up call');
  await page.locator('#a_outcome').fill('Confirmed quote request');
  await page.getByRole('button', { name: 'Log Activity', exact: true }).click();
  await expect(page.getByText('E2E follow-up call')).toBeVisible({ timeout: 10000 });

  console.log('[crm] problems:', bad.length ? bad.join(' | ') : 'NONE');
  expect(bad).toEqual([]);
});
