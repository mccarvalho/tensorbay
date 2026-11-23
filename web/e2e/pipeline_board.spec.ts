import { test, expect, type APIRequestContext } from '@playwright/test';
import { readFileSync } from 'node:fs';

// Kanban board on the Sales Pipeline: real drag & drop in a browser against a
// deployed environment. Creates its own customer + deals and removes them after.
const BASE = process.env.E2E_BASE_URL ?? 'https://dev.crm.tensorbay.io';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));
const auth = { Authorization: `Bearer ${tokens.id}` };

async function stageOf(api: APIRequestContext, id: string): Promise<string> {
  const r = await api.get(`${BASE}/v1/sales/opportunities/${id}`, { headers: auth });
  return (await r.json()).sales_stage;
}

// Wide and tall enough that all ten stage columns fit without scrolling mid-drag.
test.use({ viewport: { width: 2900, height: 1400 } });

test('pipeline board: substages, drag, hold, escrow, inventory lanes, table toggle', async ({ page, playwright }) => {
  const api = await playwright.request.newContext();
  const stamp = Date.now();
  const cust = await (await api.post(`${BASE}/v1/customers`, {
    headers: auth, data: { legal_name: `[E2E] Board ${stamp}`, status: 'PROSPECT' },
  })).json();
  const mk = async (qty: number, mrr: string, extra: Record<string, unknown> = {}) =>
    (await (await api.post(`${BASE}/v1/sales/opportunities`, {
      headers: auth,
      data: {
        customer_id: cust.id, gpu_model: 'H200', quantity: qty, duration_months: 12,
        commercial_model: 'GPU_MONTHLY', expected_mrr: mrr, probability: 30, account_owner: 'E2E', ...extra,
      },
    })).json()).id as string;
  const small = await mk(8, '1000');
  const big = await mk(64, '9000');
  const noEscrow = await mk(16, '500', { sales_stage: 'SIGNED', probability: 80, escrow_required: false });
  const noEscrowCard = () => page.getByTestId(`card-${noEscrow}`);

  try {
    await page.addInitScript((sess) => {
      localStorage.setItem('neocloud.session', JSON.stringify(sess));
      // Start from the default view once; later reloads must keep the user's choice.
      if (!sessionStorage.getItem('e2e.viewReset')) {
        localStorage.removeItem('neocloud.pipeline.view');
        sessionStorage.setItem('e2e.viewReset', '1');
      }
    }, { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now() + 3600_000 });
    const problems: string[] = [];
    page.on('pageerror', (e) => problems.push(e.message));

    await page.goto(`${BASE}/sales`, { waitUntil: 'networkidle' });

    // Board is the default view: five macro stages plus On Hold and Lost.
    const board = page.getByTestId('pipeline-board');
    await expect(board).toBeVisible();
    for (const s of ['LEAD', 'KYC', 'PAYMENT', 'DEPLOYMENT', 'ACTIVE', 'ON_HOLD', 'LOST'])
      await expect(page.getByTestId(`column-${s}`)).toBeVisible();
    await expect(page.getByTestId('column-KYC')).toContainText('Legal & Compliance');
    await expect(page.getByTestId('column-PAYMENT')).toContainText('Finance');
    for (const s of ['NEW_LEAD', 'POC', 'UNDER_REVIEW', 'AWAITING_DEPOSIT', 'ACCEPTANCE_TESTING', 'WON'])
      await expect(page.getByTestId(`substage-${s}`)).toBeVisible();

    // Both deals start in the Lead column (New Lead), biggest first.
    const lead = page.getByTestId('column-LEAD');
    await expect(lead.getByTestId(`card-${big}`)).toBeVisible();
    const order = await lead.locator('article').evaluateAll((els) => els.map((e) => e.getAttribute('data-testid')));
    expect(order.indexOf(`card-${big}`)).toBeLessThan(order.indexOf(`card-${small}`));

    // 1. Real drag & drop onto a substage row: New Lead -> Proposal Sent.
    await lead.getByTestId(`card-${big}`).dragTo(page.getByTestId('substage-PROPOSAL_SENT'));
    await expect.poll(() => stageOf(api, big)).toBe('PROPOSAL_SENT'); // persisted, not just on screen
    await expect(lead.getByTestId(`card-${big}`)).toContainText('35%');
    await expect(lead.getByTestId(`card-${big}`)).toContainText('Proposal Sent');

    // Dropping on a column body means "first substage": Lead -> KYC Screening.
    await lead.getByTestId(`card-${small}`).dragTo(page.getByTestId('column-KYC').locator('header'));
    await expect.poll(() => stageOf(api, small)).toBe('KYC_SCREENING');

    // 2. Move menu (keyboard/touch path), grouped by macro stage.
    await page.getByTestId('column-KYC').getByTestId(`card-${small}`).getByRole('combobox').selectOption('UNDER_REVIEW');
    await expect.poll(() => stageOf(api, small)).toBe('UNDER_REVIEW');
    await expect(page.getByTestId('column-KYC').getByTestId(`card-${small}`)).toContainText('65%');

    // 3. WON asks for confirmation (and is the commission trigger).
    await lead.getByTestId(`card-${big}`).getByRole('combobox').selectOption('ACCEPTANCE_TESTING');
    const inDeploy = page.getByTestId('column-DEPLOYMENT').getByTestId(`card-${big}`);
    await expect(inDeploy).toContainText('94%');
    const dialogs: string[] = [];
    page.once('dialog', (d) => { dialogs.push(d.message()); void d.dismiss(); });
    await inDeploy.dragTo(page.getByTestId('substage-WON'));
    await expect.poll(() => dialogs.length).toBe(1);
    expect(dialogs[0]).toContain('WON');
    await expect(inDeploy).toBeVisible();
    expect(await stageOf(api, big)).toBe('ACCEPTANCE_TESTING');
    page.once('dialog', (d) => { dialogs.push(d.message()); void d.accept(); });
    await inDeploy.dragTo(page.getByTestId('substage-WON'));
    await expect(page.getByTestId('column-ACTIVE').getByTestId(`card-${big}`)).toContainText('100%');
    await expect.poll(() => stageOf(api, big)).toBe('WON');

    // 4. Server refusal rolls the card back: make the PATCH fail once.
    await page.route('**/v1/sales/opportunities/*', async (route) => {
      if (route.request().method() === 'PATCH') await route.fulfill({ status: 500, body: '{"detail":"boom"}', contentType: 'application/json' });
      else await route.continue();
    });
    await page.getByTestId('column-KYC').getByTestId(`card-${small}`).dragTo(page.getByTestId('substage-SIGNED'));
    await expect(page.getByTestId('column-KYC').getByTestId(`card-${small}`)).toBeVisible({ timeout: 8000 });
    expect(await stageOf(api, small)).toBe('UNDER_REVIEW');
    await page.unroute('**/v1/sales/opportunities/*');

    // 5. On Hold keeps the probability; the card sits in the On Hold column.
    await page.getByTestId('column-KYC').getByTestId(`card-${small}`).getByRole('combobox').selectOption('ON_HOLD');
    await expect(page.getByTestId('column-ON_HOLD').getByTestId(`card-${small}`)).toContainText('65%');
    await expect.poll(() => stageOf(api, small)).toBe('ON_HOLD');

    // 6. A deal without escrow cannot enter the Payment substages.
    await expect(noEscrowCard()).toBeVisible();
    const opt = noEscrowCard().getByRole('combobox').locator('option[value="ESCROW_SETUP"]');
    await expect(opt).toBeDisabled();
    await expect(noEscrowCard()).toContainText('No escrow');

    // 7. "+" in a column opens a new-opportunity form at that column's first substage.
    await page.getByRole('button', { name: 'Add opportunity to Deployment' }).click();
    await expect(page.locator('#opp_stage')).toHaveValue('PROVISIONING');
    await expect(page.locator('#opp_prob')).toHaveValue('90'); // stage default proposed
    await expect(page.locator('#opp_escrow')).toBeChecked();
    const ym = new Date().toISOString().slice(0, 7);
    await expect(page.getByTestId('opp-folder-preview')).toContainText(`${ym}-H200-8`);
    await page.locator('#opp_short').fill('Foxgaroo GB200');
    await expect(page.getByTestId('opp-folder-preview')).toContainText(`${ym}-Foxgaroo GB200`);
    await page.keyboard.press('Escape');

    // 8. Stage filter chips narrow the board to one macro stage.
    await page.getByTestId('filter-ACTIVE').click();
    await expect(page.getByTestId('column-ACTIVE')).toBeVisible();
    await expect(page.getByTestId('column-LEAD')).toBeHidden();
    await page.getByTestId('filter-ACTIVE').click();
    await expect(page.getByTestId('column-LEAD')).toBeVisible();

    // 9. Inventory view: one lane per GPU model, deals in the macro-stage cells.
    await page.getByRole('button', { name: 'Inventory (GPU)' }).click();
    await expect(page.getByTestId('lane-H200')).toBeVisible();
    await expect(page.getByTestId('cell-H200-ACTIVE').getByTestId(`card-${big}`)).toBeVisible();
    await expect(page.getByTestId('lane-H200')).toContainText('Open demand');
    await page.screenshot({ path: '/tmp/pipeline-inventory.png', fullPage: false });

    // 10. Table view still works and the choice is remembered.
    await page.getByRole('button', { name: 'Table', exact: true }).click();
    await expect(board).toBeHidden();
    await expect(page.getByRole('cell', { name: `[E2E] Board ${stamp}` }).first()).toBeVisible();
    await page.reload({ waitUntil: 'networkidle' });
    await expect(board).toBeHidden();
    await page.getByRole('button', { name: 'Pipeline (Stage)' }).click();
    await expect(board).toBeVisible();

    expect(problems).toEqual([]);
    await page.screenshot({ path: '/tmp/pipeline-board.png', fullPage: false });
  } finally {
    for (const id of [small, big, noEscrow]) await api.delete(`${BASE}/v1/sales/opportunities/${id}`, { headers: auth });
    await api.delete(`${BASE}/v1/customers/${cust.id}`, { headers: auth });
    await api.dispose();
  }
});
