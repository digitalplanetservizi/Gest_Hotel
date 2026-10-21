/* Django console smoke test: login, static assets, read-only data and shared logout. */
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
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, locale: 'it-IT' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(base + '/admin/');
    assert(page.url().includes('/admin/login/'));
    await page.locator('[name=username]').fill(process.env.BOOTSTRAP_ADMIN_EMAIL || environment.BOOTSTRAP_ADMIN_EMAIL);
    await page.locator('[name=password]').fill(process.env.BOOTSTRAP_ADMIN_PASSWORD || environment.BOOTSTRAP_ADMIN_PASSWORD);
    await page.locator('input[type=submit]').click();
    await page.waitForURL(base + '/admin/');
    await page.getByRole('heading', { name: 'Consultazione dati · Solo superadmin' }).waitFor();
    const style = await page.request.get(base + '/static/admin/css/base.css');
    assert.equal(style.status(), 200);
    assert(style.headers()['content-type'].includes('text/css'));
    await page.screenshot({ path: path.join(artifacts, 'django-admin-desktop.png'), fullPage: true });
    const list = await page.goto(base + '/admin/hotel/user/');
    assert.equal(list.status(), 200);
    assert.equal(await page.locator('.addlink').count(), 0);
    const detailLink = page.locator('#result_list tbody tr th a').first();
    await detailLink.click();
    assert.equal(await page.locator('input[name=_save]').count(), 0);
    assert.equal(await page.locator('.deletelink').count(), 0);
    await page.locator('form[action="/admin/logout/"] button').click();
    assert.equal((await page.request.get(base + '/api/v1/auth/me/')).status(), 401);
    await page.goto(base + '/admin/hotel/user/');
    assert(page.url().includes('/admin/login/'));
    assert.deepEqual(errors, []);
    console.log('Django backend login, protected models, read-only controls, CSS and shared logout: OK');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
