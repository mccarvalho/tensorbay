import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

// The owner email is the SES mailbox simulator: the alert is really sent, but never delivered or bounced.
// Customer Order Form intake: staff create a private link, the customer (not logged in)
// fills it in, staff see it as received and can generate documents.
const BASE = process.env.E2E_BASE_URL ?? 'https://dev.crm.tensorbay.io';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));
const auth = { Authorization: `Bearer ${tokens.id}` };
test.use({ viewport: { width: 1400, height: 1400 } });

test('create the link, customer submits it logged out, staff see it received', async ({ page, browser, playwright }) => {
  test.setTimeout(120_000);
  const api = await playwright.request.newContext();
  const stamp = Date.now();
  const cust = await (await api.post(`${BASE}/v1/customers`, { headers: auth, data: { legal_name: `[E2E] Intake ${stamp}`, status: 'PROSPECT' } })).json();
  const opp = await (await api.post(`${BASE}/v1/sales/opportunities`, {
    headers: auth,
    data: {
      customer_id: cust.id, gpu_model: 'B300', quantity: 128, duration_months: 24, commercial_model: 'GPU_MONTHLY',
      expected_mrr: '800000', probability: 60, short_name: 'E2E Intake', account_owner: 'E2E', sales_stage: 'DOCS_SENT',
      account_owner_email: process.env.E2E_NOTIFY_EMAIL ?? 'success@simulator.amazonses.com',
    },
  })).json();
  try {
    await page.addInitScript((sess) => localStorage.setItem('neocloud.session', JSON.stringify(sess)),
      { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now() + 3600_000 });
    await page.goto(`${BASE}/opportunities/${opp.id}`, { waitUntil: 'networkidle' });

    // 1. Staff create the link.
    const panel = page.getByTestId('intake-panel');
    await panel.getByTestId('intake-create').click();
    const link = await panel.getByTestId('intake-link').inputValue();
    expect(link).toMatch(new RegExp(`^${BASE.replace(/[.]/g, '\\.')}/intake/[A-Za-z0-9_-]{20,}$`));

    // 2. The customer opens it in a clean browser (no session) and fills it in.
    const ctx = await browser.newContext({ viewport: { width: 1200, height: 1600 } });
    const cp = await ctx.newPage();
    const problems: string[] = [];
    cp.on('pageerror', (e) => problems.push(e.message));
    await cp.goto(link, { waitUntil: 'networkidle' });
    await expect(cp.getByRole('heading', { name: `[E2E] Intake ${stamp}` })).toBeVisible();
    await expect(cp.getByText('128 × B300')).toBeVisible();
    await expect(cp.locator('body')).not.toContainText('800000'); // no prices on the customer's page
    await expect(cp.locator('#f_legal_name')).toHaveValue(`[E2E] Intake ${stamp}`);

    // Required fields: a bad submit is stopped and says what is missing.
    await cp.locator('#f_signatory_email').fill('not-an-email');
    await cp.getByTestId('intake-submit').click();
    await expect(cp.locator('#f_company_form')).toBeFocused(); // the browser stops at the first empty required field
    await cp.locator('#f_company_form').fill('limited liability company');
    await cp.locator('#f_jurisdiction').fill('Delaware, USA');
    await cp.locator('#f_registration_number').fill('DE-123456');
    await cp.locator('#f_registered_address').fill('1 Main St\nWilmington, DE');
    await cp.locator('#f_signatory_name').fill('Jane Roe');
    await cp.locator('#f_signatory_title').fill('CEO');
    await cp.locator('#f_signatory_email').fill('jane@example.com');
    await cp.locator('#f_notices_email').fill('legal@example.com');
    await cp.locator('#f_workload_description').fill('Pre-training');
    await cp.locator('#f_compute_fabric').selectOption('INFINIBAND');
    await cp.locator('#f_shared_storage_tb').fill('250');
    await cp.getByLabel('VPN').check();
    // Typing must not lose focus between keystrokes.
    await cp.locator('#f_website').click();
    await cp.keyboard.type('https://example.com');
    await expect(cp.locator('#f_website')).toHaveValue('https://example.com');
    await cp.getByTestId('intake-submit').click();
    await expect(cp.locator('#f_confirm_accuracy')).toBeFocused(); // must confirm
    await cp.locator('#f_confirm_accuracy').check();
    await cp.getByTestId('intake-submit').click();
    await expect(cp.getByTestId('intake-done')).toBeVisible({ timeout: 15000 });

    // Opening the link again only says it was received, and shows none of the data.
    await cp.reload({ waitUntil: 'networkidle' });
    await expect(cp.getByTestId('intake-done')).toBeVisible();
    await expect(cp.locator('body')).not.toContainText('jane@example.com');
    expect(problems).toEqual([]);

    // 3. Staff see it as received, with the data.
    await page.reload({ waitUntil: 'networkidle' });
    const got = page.getByTestId('intake-submitted');
    await expect(got).toContainText('Received');
    await expect(got).toContainText('The MSA can be generated');
    await got.getByRole('button', { name: /View submitted data/ }).click();
    await expect(got).toContainText('Jane Roe');
    await expect(got).toContainText('DE-123456');
    await expect(got).toContainText('250');

    // 4. Generate the MSA from it.
    await page.locator('#deal_doc_type').selectOption('MSA');
    await page.getByRole('button', { name: 'Generate document' }).click();
    const row = page.getByTestId('deal-documents').locator('[data-testid^="doc-"]').first();
    await expect(row).toContainText('Draft · needs review', { timeout: 120_000 });
    await ctx.close();
  } finally {
    await api.delete(`${BASE}/v1/sales/opportunities/${opp.id}`, { headers: auth });
    await api.delete(`${BASE}/v1/customers/${cust.id}`, { headers: auth });
    await api.dispose();
  }
});

test('modals stay open on a click outside; Escape closes; AI Documents is gone', async ({ page }) => {
  await page.addInitScript((sess) => localStorage.setItem('neocloud.session', JSON.stringify(sess)),
    { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now() + 3600_000 });
  await page.goto(`${BASE}/sales`, { waitUntil: 'networkidle' });
  await expect(page.getByRole('link', { name: 'AI Documents' })).toHaveCount(0);
  await page.getByRole('button', { name: '+ New Opportunity' }).click();
  const dialog = page.getByRole('dialog', { name: 'New Opportunity' });
  await expect(dialog).toBeVisible();
  await page.locator('#opp_short').fill('keep me');
  // A click on the dark area outside the window, and a drag that ends there.
  await page.mouse.click(10, 300);
  await page.mouse.move(600, 400);
  await page.mouse.down();
  await page.mouse.move(5, 5);
  await page.mouse.up();
  await expect(dialog).toBeVisible();
  await expect(page.locator('#opp_short')).toHaveValue('keep me');
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  // The old page redirects; the Drive panel moved to Admin.
  await page.goto(`${BASE}/documents`, { waitUntil: 'networkidle' });
  await expect(page).toHaveURL(/\/sales$/);
  await page.goto(`${BASE}/admin`, { waitUntil: 'networkidle' });
  await expect(page.getByText(/Google Drive/i).first()).toBeVisible();
});
