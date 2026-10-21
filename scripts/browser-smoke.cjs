/* Browser verification against the running stack; no business records created.
 * Tool dependency: npm install --prefix .local/ui --no-save @playwright/test
 * Uses installed Chrome (or HOTEL_BROWSER_EXECUTABLE).
 */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const { chromium } = require(path.join(root, '.local/ui/node_modules/playwright'));
const environment = Object.fromEntries(
  fs.readFileSync(path.join(root, '.env'), 'utf8')
    .split(/\r?\n/)
    .filter(line => line && !line.startsWith('#') && line.includes('='))
    .map(line => [line.slice(0, line.indexOf('=')), line.slice(line.indexOf('=') + 1)])
);
const base = process.env.HOTEL_TEST_URL || `http://localhost:${environment.HTTP_PORT || 18080}`;

(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.HOTEL_BROWSER_EXECUTABLE
      ? { executablePath: process.env.HOTEL_BROWSER_EXECUTABLE }
      : { channel: 'chrome' }),
  });
  const artifacts = path.join(root, '.local/qa');
  fs.mkdirSync(artifacts, { recursive: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, locale: 'it-IT', timezoneId: 'Europe/Rome' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let authenticated = false;
  page.on('response', response => {
    if (authenticated && response.url().includes('/api/') && response.status() >= 400) {
      errors.push(`HTTP ${response.status()} ${new URL(response.url()).pathname}`);
    }
  });
  try {
    await page.goto(base, { waitUntil: 'networkidle' });
    await page.getByLabel('Email', { exact: true }).fill(process.env.BOOTSTRAP_ADMIN_EMAIL || environment.BOOTSTRAP_ADMIN_EMAIL);
    await page.getByLabel('Password', { exact: true }).fill(process.env.BOOTSTRAP_ADMIN_PASSWORD || environment.BOOTSTRAP_ADMIN_PASSWORD);
    await page.getByRole('button', { name: 'Accedi', exact: true }).click();
    await page.waitForURL('**/dashboard');
    await page.waitForLoadState('networkidle');
    authenticated = true;
    const sidebarColor = await page.locator('aside').evaluate(element => getComputedStyle(element).backgroundColor);
    assert.equal(sidebarColor, 'rgb(40, 48, 70)', 'Tailwind stylesheet was not applied (check CSS loading and CSP)');
    await page.screenshot({ path: path.join(artifacts, 'dashboard-desktop.png'), fullPage: true });
    const routes = ['/dashboard', '/planning', '/soggiorni/nuovo', '/cassa', '/mance', '/magazzino', '/report', '/impostazioni', '/listino', '/causali', '/utenti', '/registro-attivita'];
    for (const route of routes) {
      await page.goto(base + route, { waitUntil: 'networkidle' });
      await page.locator('h1').first().waitFor({ state: 'visible' });
      assert(!page.url().endsWith('/login'), `Unexpected logout at ${route}`);
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(base + '/dashboard', { waitUntil: 'networkidle' });
    await page.screenshot({ path: path.join(artifacts, 'dashboard-mobile.png'), fullPage: true });
    const overflow = await page.evaluate(() => ({
      width: window.innerWidth,
      scroll: document.documentElement.scrollWidth,
      elements: [...document.querySelectorAll('body *')]
        .filter(element => element.getBoundingClientRect().right > window.innerWidth + 2)
        .slice(0, 6).map(element => `${element.tagName}.${element.className}`),
    }));
    assert(overflow.scroll <= overflow.width + 2, `Mobile dashboard overflows horizontally: ${JSON.stringify(overflow)}`);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(base + '/dashboard', { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: 'Esci', exact: true }).click();
    authenticated = false;
    await page.waitForURL('**/login');
    await page.goto(base + '/cassa', { waitUntil: 'networkidle' });
    assert(page.url().endsWith('/login'), 'Protected route accessible after logout');
    assert.deepEqual(errors, [], 'Browser or API errors');
    console.log(`Browser smoke passed: login, ${routes.length} feature routes, mobile layout and logout. Screenshots: .local/qa/`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
