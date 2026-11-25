import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

// TensorBay's date standard is MM/DD/YYYY, whatever language the browser is set to.
const BASE = process.env.E2E_BASE_URL ?? 'https://dev.crm.tensorbay.io';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));
const auth = { Authorization: `Bearer ${tokens.id}` };

// A Brazilian browser: its own date fields would show DD/MM/YYYY.
test.use({ locale: 'pt-BR', timezoneId: 'America/Sao_Paulo', viewport: { width: 1700, height: 1200 } });

test('dates are typed, shown and stored as MM/DD/YYYY', async ({ page, playwright }) => {
  const api = await playwright.request.newContext();
  const cust = await (await api.post(`${BASE}/v1/customers`, { headers: auth, data: { legal_name: `[E2E] Dates ${Date.now()}`, status: 'PROSPECT' } })).json();
  let oppId: string | null = null;
  try {
    await page.addInitScript((sess) => localStorage.setItem('neocloud.session', JSON.stringify(sess)),
      { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now() + 3600_000 });
    await page.goto(`${BASE}/customers/${cust.id}`, { waitUntil: 'networkidle' });
    await page.getByTestId('customer-new-opportunity').click();
    const first = page.locator('#opp_first_delivery');
    await expect(first).toHaveAttribute('placeholder', 'MM/DD/YYYY');

    // Typing digits inserts the slashes.
    await first.click();
    await page.keyboard.type('01302027');
    await expect(first).toHaveValue('01/30/2027');
    // 11/25 is the 25th of November, not the 11th of the 25th month; a day that does not exist is refused.
    const latest = page.locator('#opp_latest_delivery');
    await latest.fill('02302027'); // Feb 30
    await expect(latest).toHaveAttribute('aria-invalid', 'true');
    await page.locator('#opp_short').click(); // leaving it puts the last good value back (empty here)
    await expect(latest).toHaveValue('');
    await latest.fill('06302027');
    await expect(latest).toHaveValue('06/30/2027');
    await expect(page.locator('#opp_start')).toHaveValue(/^\d{2}\/\d{2}\/\d{4}$/); // today's date, in the standard

    await page.locator('#opp_short').fill('E2E Dates');
    await page.locator('#opp_mrr').fill('1000');
    await page.getByRole('button', { name: 'Create Opportunity' }).click();
    await expect.poll(async () => {
      const all = await (await api.get(`${BASE}/v1/sales/opportunities?limit=200`, { headers: auth })).json();
      const o = all.find((x: { customer_id: string }) => x.customer_id === cust.id);
      oppId = o?.id ?? null;
      return o ? `${o.first_delivery_date} ${o.latest_delivery_date}` : null;
    }).toBe('2027-01-30 2027-06-30'); // stored as ISO

    // Shown back in the standard on the opportunity page and on the board card.
    await page.goto(`${BASE}/opportunities/${oppId}`, { waitUntil: 'networkidle' });
    await expect(page.getByText('Created')).toHaveCount(0);
    await page.goto(`${BASE}/sales`, { waitUntil: 'networkidle' });
    const card = page.getByTestId(`card-${oppId}`);
    await expect(card).toBeVisible();
    // Editing shows the same dates, in the standard, even in a pt-BR browser.
    await card.getByRole('button', { name: 'Edit' }).click();
    await expect(page.locator('#opp_first_delivery')).toHaveValue('01/30/2027');
    await expect(page.locator('#opp_latest_delivery')).toHaveValue('06/30/2027');
    // The calendar button is there for people who prefer to click.
    await expect(page.getByRole('button', { name: 'Open calendar' }).first()).toBeVisible();
  } finally {
    if (oppId) await api.delete(`${BASE}/v1/sales/opportunities/${oppId}`, { headers: auth });
    await api.delete(`${BASE}/v1/customers/${cust.id}`, { headers: auth });
    await api.dispose();
  }
});
