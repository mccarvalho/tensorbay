import { test, expect, type APIRequestContext } from '@playwright/test';
import { readFileSync } from 'node:fs';

// "+ New Opportunity" from a customer and from a lead: same form as the pipeline,
// and the deal shows up on the board in the chosen stage.
const BASE = process.env.E2E_BASE_URL ?? 'https://dev.crm.tensorbay.io';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));
const auth = { Authorization: `Bearer ${tokens.id}` };
test.use({ viewport: { width: 1800, height: 1300 } });

async function oppsOf(api: APIRequestContext, customerId: string) {
  const all = await (await api.get(`${BASE}/v1/sales/opportunities?limit=200`, { headers: auth })).json();
  return all.filter((o: { customer_id: string }) => o.customer_id === customerId);
}

test('add an opportunity from a customer and from a lead', async ({ page, playwright }) => {
  const api = await playwright.request.newContext();
  const stamp = Date.now();
  const cust = await (await api.post(`${BASE}/v1/customers`, {
    headers: auth, data: { legal_name: `[E2E] AddOpp ${stamp}`, status: 'PROSPECT' },
  })).json();
  const lead = await (await api.post(`${BASE}/v1/leads`, {
    headers: auth, data: { name: 'E2E Lead', email: `e2e-lead-${stamp}@example.com`, company: `[E2E] LeadCo ${stamp}`, sku_of_interest: 'B300', gpu_count: 96, region: 'Brazil' },
  })).json();
  const created: string[] = [];
  let leadCustomer: string | null = null;
  try {
    await page.addInitScript((sess) => {
      localStorage.setItem('neocloud.session', JSON.stringify(sess));
      localStorage.setItem('neocloud.pipeline.view', 'board');
    }, { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now() + 3600_000 });
    const problems: string[] = [];
    page.on('pageerror', (e) => problems.push(e.message));

    // 1. Customer page: the customer is fixed, the stage can be picked.
    await page.goto(`${BASE}/customers/${cust.id}`, { waitUntil: 'networkidle' });
    await page.getByTestId('customer-new-opportunity').click();
    await expect(page.locator('#opp_customer')).toHaveValue(cust.id);
    await expect(page.locator('#opp_customer')).toBeDisabled();
    await page.locator('#opp_short').fill('E2E From Customer');
    await page.locator('#opp_stage').selectOption('INTRO_CALL');
    await expect(page.locator('#opp_prob')).toHaveValue('20');
    await page.locator('#opp_mrr').fill('12345');
    // Order Form (V4) fields.
    await page.locator('#opp_upfront').fill('30');
    await page.locator('#opp_pay_structure').selectOption('B');
    await page.locator('#opp_first_delivery').fill('01/30/2027');
    await page.locator('#opp_latest_delivery').fill('06/30/2027');
    await page.getByRole('button', { name: 'Create Opportunity' }).click();
    await expect.poll(async () => (await oppsOf(api, cust.id)).length).toBe(1);
    const first = (await oppsOf(api, cust.id))[0];
    created.push(first.id);
    expect(first.sales_stage).toBe('INTRO_CALL');
    expect(first.short_name).toBe('E2E From Customer');
    expect(Number(first.upfront_pct)).toBe(30);
    expect(first.payment_structure).toBe('B');
    expect(first.first_delivery_date).toBe('2027-01-30');
    expect(first.latest_delivery_date).toBe('2027-06-30');
    // The related-records table on the same page updates without a reload.
    await expect(page.getByText('Intro Call').first()).toBeVisible();

    // 2. Customers list: row action opens the same form for that customer.
    await page.goto(`${BASE}/customers`, { waitUntil: 'networkidle' });
    await page.getByPlaceholder(/Search by name/).fill(`[E2E] AddOpp ${stamp}`);
    await page.getByRole('button', { name: '+ Opportunity' }).first().click();
    await expect(page.locator('#opp_customer')).toHaveValue(cust.id);
    await page.keyboard.press('Escape');

    // 3. The deal is on the pipeline board, in the Lead column, Intro Call row.
    await page.goto(`${BASE}/sales`, { waitUntil: 'networkidle' });
    await expect(page.getByTestId('column-LEAD').getByTestId(`card-${first.id}`)).toBeVisible();

    // 4. Lead: "+ Add opportunity" converts the lead, then opens the form filled in from it.
    await page.goto(`${BASE}/leads`, { waitUntil: 'networkidle' });
    await page.getByPlaceholder(/Search/).first().fill(`e2e-lead-${stamp}`).catch(() => undefined);
    await page.locator('tr', { hasText: `e2e-lead-${stamp}` }).getByRole('button', { name: 'Open' }).click();
    await page.getByTestId('lead-add-opportunity').click();
    await expect(page.locator('#cv_opp')).toBeChecked();
    await page.getByRole('button', { name: 'Convert and add opportunity' }).click();
    await expect(page.locator('#opp_short')).toHaveValue(`[E2E] LeadCo ${stamp}`);
    await expect(page.locator('#opp_model')).toHaveValue('B300');
    await expect(page.locator('#opp_qty')).toHaveValue('96');
    await expect(page.locator('#opp_region')).toHaveValue('Brazil');
    await expect(page.locator('#opp_customer')).toBeDisabled();
    await page.locator('#opp_mrr').fill('50000');
    await page.getByRole('button', { name: 'Create Opportunity' }).click();
    await expect(page).toHaveURL(/\/customers\//, { timeout: 15000 });
    leadCustomer = page.url().split('/customers/')[1];
    await expect.poll(async () => (await oppsOf(api, leadCustomer!)).length).toBe(1);
    const second = (await oppsOf(api, leadCustomer!))[0];
    created.push(second.id);
    expect(second.sales_stage).toBe('NEW_LEAD');
    expect(second.quantity).toBe(96);
    expect(problems).toEqual([]);
  } finally {
    for (const id of created) await api.delete(`${BASE}/v1/sales/opportunities/${id}`, { headers: auth });
    await api.delete(`${BASE}/v1/customers/${cust.id}`, { headers: auth });
    if (leadCustomer) await api.delete(`${BASE}/v1/customers/${leadCustomer}`, { headers: auth });
    await api.dispose();
  }
});
