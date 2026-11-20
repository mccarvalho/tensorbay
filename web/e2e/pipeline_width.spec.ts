import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

// The Sales Pipeline uses the full content width (other pages keep the 1280px
// column), the board scrolls inside itself, and the page never scrolls sideways.
const BASE = process.env.E2E_BASE_URL ?? 'https://dev.crm.tensorbay.io';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));

for (const [w, h] of [[1280, 800], [1512, 982], [1920, 1080], [2560, 1440]] as const) {
  test(`pipeline width at ${w}x${h}`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await page.addInitScript((sess) => {
      localStorage.setItem('neocloud.session', JSON.stringify(sess));
      localStorage.setItem('neocloud.pipeline.view', 'board');
    }, { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now() + 3600_000 });

    await page.goto(`${BASE}/sales`, { waitUntil: 'networkidle' });
    const board = page.getByTestId('pipeline-board');
    await expect(board).toBeVisible();
    const m = await page.evaluate(() => {
      const b = document.querySelector('[data-testid="pipeline-board"]') as HTMLElement;
      const main = document.querySelector('main') as HTMLElement;
      const cols = [...b.querySelectorAll('[data-testid^="column-"]')] as HTMLElement[];
      const br = b.getBoundingClientRect();
      const visible = cols.filter((c) => { const r = c.getBoundingClientRect(); return r.left >= br.left - 1 && r.right <= br.right + 1; }).length;
      return {
        boardW: b.clientWidth, boardScrollW: b.scrollWidth, mainInnerW: main.clientWidth,
        pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
        colW: Math.round(cols[0].getBoundingClientRect().width), visible, total: cols.length,
      };
    });
    console.log(`[width] ${w}px: board ${m.boardW}px, columns fully visible ${m.visible}/${m.total}, column ${m.colW}px`);
    expect(m.total).toBe(10);
    expect(m.pageOverflow).toBeLessThanOrEqual(0);           // no sideways page scroll
    expect(m.mainInnerW - m.boardW).toBeLessThanOrEqual(64);  // board fills the content area (minus padding)
    if (w >= 1512) expect(m.boardW).toBeGreaterThan(1280);    // wider than the old cap
    if (w >= 2560) expect(m.visible).toBe(10);                // everything fits on a 2560 screen

    // Other pages keep the 1280px reading column.
    await page.goto(`${BASE}/customers`, { waitUntil: 'networkidle' });
    const cw = await page.getByTestId('page-container').evaluate((e) => e.clientWidth);
    expect(cw).toBeLessThanOrEqual(1280);
  });
}
