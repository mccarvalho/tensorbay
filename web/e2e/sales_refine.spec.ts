import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const BASE = process.env.E2E_BASE_URL ?? 'https://d22xy9yyfwju3n.cloudfront.net';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));
test('opportunity form: GPU combobox has VR720 + owner prefilled', async ({ page }) => {
  const s = { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now()+3600_000 };
  await page.addInitScript((sess) => { localStorage.setItem('neocloud.session', JSON.stringify(sess)); }, s);
  await page.goto(`${BASE}/sales`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.getByRole('button', { name: '+ New Opportunity' }).click();

  // datalist options include VR720 and other NVIDIA models
  const opts = await page.locator('#gpu-model-options option').evaluateAll(
    (els) => els.map((e) => (e as HTMLOptionElement).value),
  );
  console.log('[refine] gpu model options:', opts.join(', '));
  expect(opts).toContain('VR720');
  expect(opts).toContain('H200');
  expect(opts).toContain('GB200');

  // account owner prefilled with signed-in user's name (from idToken claims)
  const owner = await page.locator('#opp_owner').inputValue();
  console.log('[refine] account owner prefilled:', JSON.stringify(owner));
  expect(owner.length).toBeGreaterThan(0);
});
