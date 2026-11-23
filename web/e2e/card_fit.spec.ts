import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

// Cards must never spill outside their column, whatever the text lengths.
const BASE = process.env.E2E_BASE_URL ?? 'https://dev.crm.tensorbay.io';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));
const auth = { Authorization: `Bearer ${tokens.id}` };

for (const w of [1280, 1600, 2000]) {
  test(`cards fit their column at ${w}px`, async ({ page, playwright }) => {
    await page.setViewportSize({ width: w, height: 1300 });
    const api = await playwright.request.newContext();
    const cust = await (await api.post(`${BASE}/v1/customers`, {
      headers: auth, data: { legal_name: `[E2E] Fit Customer With A Very Long Legal Name Industries Ltda ${w}`, status: 'PROSPECT' },
    })).json();
    const ids: string[] = [];
    const mk = async (stage: string, extra: Record<string, unknown> = {}) => {
      const o = await (await api.post(`${BASE}/v1/sales/opportunities`, {
        headers: auth,
        data: {
          customer_id: cust.id, gpu_model: 'HGX B300 Liquid-Cooled', quantity: 1024, duration_months: 36,
          commercial_model: 'RESERVED_CLUSTER_PREPAID', expected_mrr: '98759424.55', probability: 65,
          short_name: 'Positivo Manaus to Ascenty SP lot one', account_owner: 'Maurício de Carvalho Junior',
          region: 'Brazil (São Paulo - Ascenty SP5 campus)', assigned_to: 'Lizi Santucci de Albuquerque',
          next_action: 'Review MSA & Order Form with Legal and send to customer', expected_start: '2027-01-28',
          sales_stage: stage, ...extra,
        },
      })).json();
      ids.push(o.id);
    };
    await mk('DOCS_SENT'); await mk('READY_FOR_TESTING'); await mk('SUPPORT_SLA'); await mk('ON_HOLD', { escrow_required: false });
    try {
      await page.addInitScript((sess) => {
        localStorage.setItem('neocloud.session', JSON.stringify(sess));
        localStorage.setItem('neocloud.pipeline.view', 'board');
      }, { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now() + 3600_000 });
      await page.goto(`${BASE}/sales`, { waitUntil: 'networkidle' });
      const bad = await page.evaluate((cardIds) => {
        const out: string[] = [];
        for (const id of cardIds) {
          const card = document.querySelector(`[data-testid="card-${id}"]`) as HTMLElement | null;
          if (!card) { out.push(`${id}: missing`); continue; }
          const cr = card.getBoundingClientRect();
          if (card.scrollWidth > card.clientWidth + 1) out.push(`${id}: card scrollWidth ${card.scrollWidth} > ${card.clientWidth}`);
          for (const el of card.querySelectorAll<HTMLElement>('*')) {
            if (el.closest('.truncate') && !el.classList.contains('truncate')) continue; // clipped on purpose, with an ellipsis
            const r = el.getBoundingClientRect();
            if (r.width && (r.right > cr.right + 1 || r.left < cr.left - 1))
              out.push(`${id}: <${el.tagName.toLowerCase()}> "${(el.textContent ?? '').slice(0, 40)}" spills ${Math.round(r.right - cr.right)}px`);
          }
        }
        for (const k of document.querySelectorAll<HTMLElement>('.card-glow')) {
          if (k.scrollWidth > k.clientWidth + 1) out.push(`KPI "${k.textContent?.slice(0, 30)}" overflows ${k.scrollWidth - k.clientWidth}px`);
          for (const v of k.querySelectorAll<HTMLElement>('span')) if (v.scrollWidth > v.clientWidth + 1) out.push(`KPI value "${v.textContent?.slice(0, 20)}" clipped`);
        }
        return out;
      }, ids);
      await page.screenshot({ path: `/tmp/card-fit-${w}.png` });
      expect(bad).toEqual([]);
    } finally {
      for (const id of ids) await api.delete(`${BASE}/v1/sales/opportunities/${id}`, { headers: auth });
      await api.delete(`${BASE}/v1/customers/${cust.id}`, { headers: auth });
      await api.dispose();
    }
  });
}
