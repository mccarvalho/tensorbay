import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

// The opportunity window: wide, two columns, never taller than the screen.
const BASE = process.env.E2E_BASE_URL ?? 'https://dev.crm.tensorbay.io';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8'));

for (const [w, h] of [[1280, 720], [1676, 900], [900, 700]] as const) {
  test(`opportunity window fits a ${w}x${h} screen`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await page.addInitScript((sess) => localStorage.setItem('neocloud.session', JSON.stringify(sess)),
      { accessToken: tokens.access, idToken: tokens.id, refreshToken: tokens.refresh, expiresAt: Date.now() + 3600_000 });
    await page.goto(`${BASE}/sales`, { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: '+ New Opportunity' }).click();
    const dialog = page.getByRole('dialog', { name: 'New Opportunity' });
    await expect(dialog).toBeVisible();

    const box = (await dialog.boundingBox())!;
    expect(box.y).toBeGreaterThanOrEqual(0);
    expect(box.y + box.height).toBeLessThanOrEqual(h + 1); // never taller than the screen
    // Title and the action buttons are always reachable.
    await expect(dialog.getByRole('heading', { name: 'New Opportunity' })).toBeInViewport();
    await expect(dialog.getByRole('button', { name: 'Create Opportunity' })).toBeInViewport();
    await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeInViewport();

    const left = (await page.locator('#opp_customer').boundingBox())!;
    const right = (await page.locator('#opp_stage').boundingBox())!;
    if (w >= 1024) {
      expect(box.width).toBeGreaterThan(900);            // wide
      expect(right.x).toBeGreaterThan(left.x + left.width - 1); // stage sits in the second column
      expect(Math.abs(right.y - left.y)).toBeLessThan(120);     // starting at the same height
    } else {
      expect(right.y).toBeGreaterThan(left.y);           // narrow screens stack the columns
    }
    // Everything is reachable by scrolling inside the window.
    await dialog.locator('#opp_escrow').scrollIntoViewIfNeeded();
    await expect(dialog.locator('#opp_escrow')).toBeInViewport();
    await expect(dialog.getByRole('button', { name: 'Create Opportunity' })).toBeInViewport();
  });
}
