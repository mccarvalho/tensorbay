import { test } from '@playwright/test';
const BASE = process.env.E2E_BASE_URL ?? 'https://d22xy9yyfwju3n.cloudfront.net';
const ROUTES = ['/', '/customers', '/admin', '/documents', '/callback'];
for (const r of ROUTES) {
  test(`incognito deep-link ${r}`, async ({ page }) => {
    const errs: string[] = [];
    page.on('console', (m) => { if (m.type() === 'error') errs.push('CONSOLE: ' + m.text()); });
    page.on('pageerror', (e) => errs.push('PAGEERR: ' + e.message));
    await page.goto(`${BASE}${r}`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(1200);
    const body = (await page.locator('body').innerText()).slice(0, 120).replace(/\n/g, ' ');
    console.log(`[${r}] url=${page.url().replace(BASE,'')} errs=${errs.length} | ${body}`);
    errs.forEach((e) => console.log(`   ${r} ${e}`));
  });
}
