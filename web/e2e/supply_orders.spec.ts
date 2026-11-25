import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

// Register a GPU purchase by totals (the Positivo HGX B300 order) through the UI,
// with a first dated lot and the rest unscheduled, and check the forecast a
// salesperson sees. Cleans up after itself.
const BASE = process.env.E2E_BASE_URL ?? 'https://dev.crm.tensorbay.io';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));
const auth = { Authorization: `Bearer ${tokens.id}` };

test.use({ viewport: { width: 1600, height: 1300 } });

test('supply order by totals + forecast', async ({ page, playwright }) => {
  const api = await playwright.request.newContext();
  const ref = `[E2E] Positivo ${Date.now()}`;
  const problems: string[] = [];
  page.on('pageerror', (e) => problems.push(e.message));
  await page.addInitScript((sess) => localStorage.setItem('neocloud.session', JSON.stringify(sess)),
    { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now() + 3600_000 });

  let orderId: string | undefined;
  try {
    await page.goto(`${BASE}/capacity`, { waitUntil: 'networkidle' });
    await expect(page.getByTestId('supply-forecast')).toBeVisible();
    await page.getByRole('button', { name: '+ New supply order' }).click();

    await page.locator('#so_ref').fill(ref);
    await page.locator('#so_model').fill('B300-E2E');
    await page.locator('#so_srv').fill('Supermicro SYS-822GS-NB3RT');
    await page.locator('#so_n').fill('64');
    await expect(page.getByTestId('so-total-gpus')).toHaveText('512 GPUs');
    await page.locator('#so_price').fill('806101.73');
    await page.locator('#so_total').fill('51590510.51');
    await page.locator('#so_dst').fill('Ascenty SP');
    await page.locator('#so_tax').fill('REDATA');
    // First lot: 16 servers on 30 Jan; the other 48 stay "no date yet".
    await page.getByLabel('Lot 1 name').fill('Lote 1');
    await page.getByLabel('Lot 1 servers').fill('16');
    await page.getByLabel('Lot 1 expected delivery').fill('01/30/2027');
    await expect(page.getByText('48 servers without a date')).toBeVisible();
    await page.getByRole('button', { name: 'Create order' }).click();

    const card = page.locator('article', { hasText: ref });
    await expect(card).toBeVisible();
    orderId = (await card.getAttribute('data-testid'))!.replace('order-', '');
    await expect(card).toContainText('512 GPUs');
    await expect(card).toContainText('$51,590,510.51');
    await expect(card).toContainText('Lote 1');
    await expect(card).toContainText('16 servers · 128 GPUs');
    await expect(card).toContainText('Remaining (no date yet)');
    await expect(card).toContainText('48 servers · 384 GPUs');
    await expect(card).toContainText('Next delivery: 01/30/2027');

    // Forecast row for the model: 512 contracted, 384 without date, +128 in Jan 2027.
    const row = page.getByTestId('forecast-B300-E2E');
    await expect(row).toBeVisible();
    await expect(row).toContainText('512');
    await expect(row).toContainText('384');
    await expect(row).toContainText('+128');

    // Mark lot 1 delivered through the lot editor.
    await card.getByRole('row', { name: /Lote 1/ }).getByRole('button', { name: 'Edit' }).click();
    await page.locator('#lot_ad').fill('02/02/2027');
    await page.getByRole('button', { name: 'Save lot' }).click();
    await expect(card.getByRole('row', { name: /Lote 1/ })).toContainText('DELIVERED');
    await expect(card).toContainText('128 delivered');

    expect(problems).toEqual([]);
    await page.screenshot({ path: '/tmp/supply-orders.png', fullPage: false });
  } finally {
    if (orderId) {
      // Delivered lots protect the order, so roll the lot back first, then delete.
      const o = await (await api.get(`${BASE}/v1/capacity/orders/${orderId}`, { headers: auth })).json();
      for (const l of o.lots) {
        await api.patch(`${BASE}/v1/capacity/orders/${orderId}/lots/${l.id}`, {
          headers: auth, data: { status: 'ORDERED', actual_delivery: null, actual_operational: null },
        });
      }
      const del = await api.delete(`${BASE}/v1/capacity/orders/${orderId}`, { headers: auth });
      expect(del.status()).toBe(204);
    }
    await api.dispose();
  }
});
