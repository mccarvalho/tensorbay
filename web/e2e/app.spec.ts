import { test, expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';

const BASE = process.env.E2E_BASE_URL ?? 'https://d22xy9yyfwju3n.cloudfront.net';
const tokens = JSON.parse(readFileSync('/tmp/e2e_tokens.json', 'utf8')) as {
  access: string;
  id: string;
  refresh: string;
  exp: number;
};

// Matches the shape auth.ts stores under localStorage['neocloud.session'].
const session = {
  accessToken: tokens.access,
  idToken: tokens.id,
  refreshToken: tokens.refresh,
  expiresAt: Date.now() + (tokens.exp ?? 3600) * 1000,
};

const PAGES = [
  { path: '/', name: 'Dashboard' },
  { path: '/customers', name: 'Customers' },
  { path: '/contracts', name: 'Contracts' },
  { path: '/inventory', name: 'Inventory' },
  { path: '/capacity', name: 'Capacity' },
  { path: '/reservations', name: 'Reservations' },
  { path: '/documents', name: 'Documents' },
  { path: '/admin', name: 'Admin' },
];

interface Captured {
  consoleErrors: string[];
  pageErrors: string[];
  badResponses: string[];
}

function wire(page: Page): Captured {
  const cap: Captured = { consoleErrors: [], pageErrors: [], badResponses: [] };
  page.on('console', (m) => {
    if (m.type() === 'error') cap.consoleErrors.push(m.text());
  });
  page.on('pageerror', (e) => cap.pageErrors.push(e.message));
  page.on('response', async (resp) => {
    const url = resp.url();
    if (!url.includes('/v1/') && !url.endsWith('/health')) return;
    const ct = resp.headers()['content-type'] ?? '';
    const status = resp.status();
    if (status >= 400 || (ct.includes('text/html') && url.includes('/v1/'))) {
      cap.badResponses.push(`${status} ${ct.split(';')[0]} ${url}`);
    }
  });
  return cap;
}

test('SPA loads session and all pages fetch JSON (no HTML/parse errors)', async ({ page }) => {
  // Seed the session before any app code runs.
  await page.addInitScript((s) => {
    window.localStorage.setItem('neocloud.session', JSON.stringify(s));
  }, session);

  const results: Record<string, Captured> = {};

  for (const p of PAGES) {
    const cap = wire(page);
    await page.goto(`${BASE}${p.path}`, { waitUntil: 'networkidle', timeout: 30000 });
    // Give react-query a beat to settle any in-flight fetches.
    await page.waitForTimeout(1500);
    results[p.name] = cap;
    // Remove listeners for the next iteration.
    page.removeAllListeners('console');
    page.removeAllListeners('pageerror');
    page.removeAllListeners('response');
  }

  // Report everything to stdout for diagnosis.
  console.log('\n==== E2E RESULTS ====');
  let anyFail = false;
  for (const p of PAGES) {
    const r = results[p.name];
    const probs = [
      ...r.pageErrors.map((e) => `PAGEERR: ${e}`),
      ...r.consoleErrors.map((e) => `CONSOLE: ${e}`),
      ...r.badResponses.map((e) => `BADRESP: ${e}`),
    ];
    if (probs.length) {
      anyFail = true;
      console.log(`\n[${p.name}] ${p.path}  ❌`);
      probs.slice(0, 8).forEach((x) => console.log('   ' + x));
    } else {
      console.log(`[${p.name}] ${p.path}  ✅`);
    }
  }
  console.log('==== END ====\n');

  expect(anyFail, 'one or more pages had errors — see log above').toBe(false);
});
