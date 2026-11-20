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

test('pipeline board: drag, move menu, confirmations, rollback, table toggle', async ({ page, playwright }) => {
  const api = await playwright.request.newContext();
  const stamp = Date.now();
  const cust = await (await api.post(`${BASE}/v1/customers`, {
    headers: auth, data: { legal_name: `[E2E] Board ${stamp}`, status: 'PROSPECT' },
  })).json();
  const mk = async (qty: number, mrr: string) =>
    (await (await api.post(`${BASE}/v1/sales/opportunities`, {
      headers: auth,
      data: {
        customer_id: cust.id, gpu_model: 'H200', quantity: qty, duration_months: 12,
        commercial_model: 'GPU_MONTHLY', expected_mrr: mrr, probability: 30, account_owner: 'E2E',
      },
    })).json()).id as string;
  const small = await mk(8, '1000');
  const big = await mk(64, '9000');

  try {
    await page.addInitScript((sess) => {
      localStorage.setItem('neocloud.session', JSON.stringify(sess));
      localStorage.removeItem('neocloud.pipeline.view');
    }, { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now() + 3600_000 });
    const problems: string[] = [];
    page.on('pageerror', (e) => problems.push(e.message));

    await page.goto(`${BASE}/sales`, { waitUntil: 'networkidle' });

    // Board is the default view with all six stage columns.
    const board = page.getByTestId('pipeline-board');
    await expect(board).toBeVisible();
    for (const s of ['PROSPECTING', 'QUALIFICATION', 'PROPOSAL', 'NEGOTIATION', 'WON', 'LOST'])
      await expect(page.getByTestId(`column-${s}`)).toBeVisible();

    // Both deals start in Prospecting, biggest first.
    const prospecting = page.getByTestId('column-PROSPECTING');
    await expect(prospecting.getByTestId(`card-${big}`)).toBeVisible();
    const order = await prospecting.locator('article').evaluateAll((els) => els.map((e) => e.getAttribute('data-testid')));
    expect(order.indexOf(`card-${big}`)).toBeLessThan(order.indexOf(`card-${small}`));

    // 1. Real drag & drop: Prospecting -> Qualification.
    await prospecting.getByTestId(`card-${big}`).dragTo(page.getByTestId('column-QUALIFICATION'));
    await expect(page.getByTestId('column-QUALIFICATION').getByTestId(`card-${big}`)).toBeVisible();
    await expect.poll(() => stageOf(api, big)).toBe('QUALIFICATION'); // persisted, not just on screen

    // 2. Move menu (keyboard/touch path).
    await prospecting.getByTestId(`card-${small}`).getByRole('combobox').selectOption('PROPOSAL');
    await expect(page.getByTestId('column-PROPOSAL').getByTestId(`card-${small}`)).toBeVisible();
    await expect.poll(() => stageOf(api, small)).toBe('PROPOSAL');

    // 3. WON asks for confirmation: dismissing it moves nothing.
    page.once('dialog', (d) => d.dismiss());
    await page.getByTestId('column-QUALIFICATION').getByTestId(`card-${big}`).dragTo(page.getByTestId('column-WON'));
    await page.waitForTimeout(600);
    await expect(page.getByTestId('column-QUALIFICATION').getByTestId(`card-${big}`)).toBeVisible();
    expect(await stageOf(api, big)).toBe('QUALIFICATION');
    //    ...accepting it does.
    page.once('dialog', (d) => d.accept());
    await page.getByTestId('column-QUALIFICATION').getByTestId(`card-${big}`).dragTo(page.getByTestId('column-WON'));
    await expect(page.getByTestId('column-WON').getByTestId(`card-${big}`)).toBeVisible();
    await expect.poll(() => stageOf(api, big)).toBe('WON');

    // 4. Server refusal rolls the card back: make the PATCH fail once.
    await page.route('**/v1/sales/opportunities/*', async (route) => {
      if (route.request().method() === 'PATCH') await route.fulfill({ status: 500, body: '{"detail":"boom"}', contentType: 'application/json' });
      else await route.continue();
    });
    await page.getByTestId('column-PROPOSAL').getByTestId(`card-${small}`).dragTo(page.getByTestId('column-NEGOTIATION'));
    await expect(page.getByTestId('column-PROPOSAL').getByTestId(`card-${small}`)).toBeVisible({ timeout: 8000 });
    expect(await stageOf(api, small)).toBe('PROPOSAL');
    await page.unroute('**/v1/sales/opportunities/*');

    // 5. "+" in a column opens a new-opportunity form preset to that stage.
    await page.getByRole('button', { name: 'Add opportunity to Negotiation' }).click();
    await expect(page.locator('#opp_stage')).toHaveValue('NEGOTIATION');
    await page.keyboard.press('Escape');

    // 6. Table view still works and the choice is remembered.
    await page.getByRole('button', { name: 'Table', exact: true }).click();
    await expect(board).toBeHidden();
    await expect(page.getByRole('cell', { name: `[E2E] Board ${stamp}` }).first()).toBeVisible();
    await page.reload({ waitUntil: 'networkidle' });
    await expect(board).toBeHidden();
    await page.getByRole('button', { name: 'Board', exact: true }).click();
    await expect(board).toBeVisible();

    expect(problems).toEqual([]);
    await page.screenshot({ path: '/tmp/pipeline-board.png', fullPage: false });
  } finally {
    for (const id of [small, big]) await api.delete(`${BASE}/v1/sales/opportunities/${id}`, { headers: auth });
    await api.delete(`${BASE}/v1/customers/${cust.id}`, { headers: auth });
    await api.dispose();
  }
});
