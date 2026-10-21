/* Read-only UI smoke test, plus a signed backup download. No restore or license changes. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const { chromium } = require(path.join(root, '.local/ui/node_modules/playwright'));
const environment = Object.fromEntries(
  fs.readFileSync(path.join(root, '.env'), 'utf8').split(/\r?\n/)
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
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, locale: 'it-IT', timezoneId: 'Europe/Rome' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(base + '/login');
    await page.getByLabel('Email', { exact: true }).fill(process.env.BOOTSTRAP_ADMIN_EMAIL || environment.BOOTSTRAP_ADMIN_EMAIL);
    await page.getByLabel('Password', { exact: true }).fill(process.env.BOOTSTRAP_ADMIN_PASSWORD || environment.BOOTSTRAP_ADMIN_PASSWORD);
    await page.getByRole('button', { name: 'Accedi', exact: true }).click();
    await page.waitForURL('**/dashboard');
    await page.getByRole('link', { name: 'Superadmin', exact: true }).click();
    await page.getByRole('heading', { name: 'Superadmin', exact: true }).waitFor();
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: 'Salva licenza', exact: true }).waitFor();
    assert(await page.getByRole('button', { name: 'Ripristina dati', exact: true }).isDisabled());
    assert(await page.getByText('Stato: Attiva', { exact: true }).isVisible());
    await page.screenshot({ path: path.join(artifacts, 'superadmin-desktop.png'), fullPage: true });
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: 'Scarica backup', exact: true }).click(),
    ]);
    const backup = JSON.parse(fs.readFileSync(await download.path(), 'utf8'));
    assert.equal(backup.format, 'hotel-business-backup-v1');
    assert.equal(typeof backup.signed_data, 'string');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForFunction(() => document.querySelector('aside').getBoundingClientRect().right <= 1);
    await page.screenshot({ path: path.join(artifacts, 'superadmin-mobile.png'), fullPage: true });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2));
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.getByRole('link', { name: 'Utenti', exact: true }).click();
    await page.getByRole('button', { name: '+ Utente', exact: true }).click();
    const options = await page.getByLabel('Ruolo').locator('option').allTextContents();
    assert.deepEqual(options, ['Operatore', 'Amministratore', 'Superadmin']);
    assert.deepEqual(errors, []);
    console.log('Superadmin UI, three role choices, signed download and mobile layout: OK');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
