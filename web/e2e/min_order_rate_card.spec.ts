import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

// Opportunity form: GPUs in multiples of 8, the 32-server minimum note, and the list price from the rate card.
const BASE = process.env.E2E_BASE_URL ?? 'https://dev.crm.tensorbay.io';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));

test('quantity step, minimum order note and list price', async ({ page }) => {
  await page.addInitScript((sess) => {
    localStorage.setItem('neocloud.session', JSON.stringify(sess));
  }, { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now() + 3600_000 });
  await page.goto(`${BASE}/sales`, { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: '+ New Opportunity' }).click();
  const submit = page.getByRole('button', { name: 'Create Opportunity' });

  await page.locator('#opp_qty').fill('100');
  await expect(page.getByTestId('qty-step-error')).toContainText('multiple of 8');
  await expect(submit).toBeDisabled();

  await page.locator('#opp_qty').fill('128');
  await expect(page.getByTestId('qty-step-error')).toHaveCount(0);
  await expect(page.getByTestId('qty-min-note')).toContainText('32 servers (256 GPUs)');

  await page.locator('#opp_qty').fill('512');
  await expect(page.getByTestId('qty-min-note')).toHaveCount(0);

  await page.locator('#opp_model').fill('HGX B300');
  await page.locator('#opp_term').fill('36');
  await page.locator('#opp_upfront').fill('65');
  const hint = page.getByTestId('list-price');
  await expect(hint).toContainText('US$ 6.44');
  await hint.getByRole('button').click();
  const mrr = Number(await page.locator('#opp_mrr').inputValue());
  expect(Math.round(mrr)).toBe(Math.round(6.44 * 512 * 730));
  await page.screenshot({ path: '/tmp/min_order.png' });
});
