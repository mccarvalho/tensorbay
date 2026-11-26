import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

// Sales Pipeline: availability summary on the page and the full list in a modal.
const BASE = process.env.E2E_BASE_URL ?? 'https://dev.crm.tensorbay.io';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));

test('availability summary and modal on the sales pipeline', async ({ page }) => {
  await page.addInitScript((sess) => {
    localStorage.setItem('neocloud.session', JSON.stringify(sess));
  }, { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now() + 3600_000 });
  await page.goto(`${BASE}/sales`, { waitUntil: 'networkidle' });
  const box = page.getByTestId('availability-summary');
  await expect(box).toBeVisible();
  await expect(box).toContainText('Available now');
  await expect(box).toContainText('A100');
  await expect(box).toContainText('1,400 GPUs');
  await expect(box).toContainText('Coming');
  await page.screenshot({ path: '/tmp/avail_summary.png' });

  await page.getByTestId('availability-open').click();
  const modal = page.getByTestId('availability-modal');
  await expect(modal).toBeVisible();
  await expect(modal).toContainText('Immediate');
  await expect(modal).toContainText('March 2027');
  await expect(modal).toContainText('VR200');
  await expect(modal).toContainText('16 racks');
  await expect(modal.locator('span.badge').first()).toHaveText('Immediate');  // immediate comes first
  await page.waitForTimeout(600);
  await page.screenshot({ path: '/tmp/avail_modal.png' });
  await page.getByRole('button', { name: 'Close', exact: true }).last().click();
  await expect(modal).toBeHidden();
});
