import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

// Deal documents on the opportunity page: generate from the UI, wait for the
// background job, download the DOCX and see the Drive link. Uses a real model call.
const BASE = process.env.E2E_BASE_URL ?? 'https://dev.crm.tensorbay.io';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));
const auth = { Authorization: `Bearer ${tokens.id}` };

test.use({ viewport: { width: 1600, height: 1200 } });

test('opportunity page: generate a proposal, download the DOCX, open it in Drive', async ({ page, playwright }) => {
  test.setTimeout(150_000);
  const api = await playwright.request.newContext();
  const cust = await (await api.post(`${BASE}/v1/customers`, {
    headers: auth, data: { legal_name: `[E2E] Docs UI ${Date.now()}`, status: 'PROSPECT', country: 'BR' },
  })).json();
  const opp = await (await api.post(`${BASE}/v1/sales/opportunities`, {
    headers: auth,
    data: {
      customer_id: cust.id, gpu_model: 'B300', quantity: 64, duration_months: 24, commercial_model: 'GPU_MONTHLY',
      expected_mrr: '250000', probability: 35, short_name: 'E2E UI Docs', account_owner: 'E2E', sales_stage: 'PROPOSAL_SENT',
    },
  })).json();
  try {
    await page.addInitScript((sess) => localStorage.setItem('neocloud.session', JSON.stringify(sess)),
      { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now() + 3600_000 });
    const problems: string[] = [];
    page.on('pageerror', (e) => problems.push(e.message));

    await page.goto(`${BASE}/opportunities/${opp.id}`, { waitUntil: 'networkidle' });
    const panel = page.getByTestId('deal-documents');
    await expect(panel).toBeVisible();
    await expect(panel).toContainText('No documents yet');

    await panel.locator('#deal_doc_type').selectOption('PROPOSAL');
    await panel.locator('#deal_doc_notes').fill('Prepayment 30% on signature');
    await panel.getByRole('button', { name: 'Generate document' }).click();

    // A row appears at once as "Generating…", then becomes a draft that needs review.
    const row = panel.locator('[data-testid^="doc-"]').first();
    await expect(row).toContainText('v1');
    await expect(row).toContainText('Draft · needs review', { timeout: 120_000 });
    await expect(row).toContainText('Proposal - [E2E] Docs UI');
    await expect(row.getByRole('link', { name: 'Open in Drive' })).toHaveAttribute('href', /docs\.google\.com|drive\.google\.com/);

    const [download] = await Promise.all([
      page.waitForEvent('download'),
      row.getByRole('button', { name: 'Download DOCX' }).click(),
    ]);
    expect(download.suggestedFilename()).toMatch(/^Proposal - \[E2E\] Docs UI .* - v1 - \d{4}-\d{2}-\d{2}\.docx$/);
    const path = await download.path();
    expect(readFileSync(path!).subarray(0, 2).toString()).toBe('PK'); // a real DOCX (zip)

    // Approve, then a second generation is v2 on top.
    await row.getByRole('button', { name: 'Approve' }).click();
    await expect(row).toContainText('Approved');

    // The board card links to this panel.
    await page.goto(`${BASE}/sales`, { waitUntil: 'networkidle' });
    await page.getByTestId(`card-${opp.id}`).getByRole('link', { name: 'Documents' }).click();
    await expect(page).toHaveURL(new RegExp(`/opportunities/${opp.id}#documents`));
    expect(problems).toEqual([]);
    await page.screenshot({ path: '/tmp/deal-documents.png' });
  } finally {
    await api.delete(`${BASE}/v1/sales/opportunities/${opp.id}`, { headers: auth });
    await api.delete(`${BASE}/v1/customers/${cust.id}`, { headers: auth });
    await api.dispose();
  }
});
