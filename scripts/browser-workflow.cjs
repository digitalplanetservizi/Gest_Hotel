/* MUTATING acceptance test. Refuses to run outside disposable localhost:18081.
 * Start a separate Compose project and empty database first. No real guest data.
 */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const { chromium } = require(path.join(root, '.local/ui/node_modules/playwright'));
const base = process.env.HOTEL_E2E_URL;
assert(['http://127.0.0.1:18081', 'http://localhost:18081'].includes(base), 'Set HOTEL_E2E_URL to the disposable test stack on port 18081');
const env = Object.fromEntries(fs.readFileSync(path.join(root, '.env'), 'utf8').split(/\r?\n/)
  .filter(line => line && !line.startsWith('#') && line.includes('='))
  .map(line => [line.slice(0, line.indexOf('=')), line.slice(line.indexOf('=') + 1)]));
const dateParts = new Intl.DateTimeFormat('en', { timeZone: 'Europe/Rome', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
const datePart = name => dateParts.find(part => part.type === name).value;
const day = `${datePart('year')}-${datePart('month')}-${datePart('day')}`;
const next = new Date(day + 'T12:00:00Z');
next.setUTCDate(next.getUTCDate() + 1);
const nextDay = next.toISOString().slice(0, 10);

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, locale: 'it-IT', timezoneId: 'Europe/Rome' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  async function api(resource, method = 'GET', body) {
    return page.evaluate(async ({ resource, method, body }) => {
      const token = document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.split('=')[1] || '';
      const response = await fetch('/api/v1/' + resource, {
        method,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      const json = await response.json();
      if (!response.ok) throw new Error(`${resource}: ${response.status}: ${JSON.stringify(json)}`);
      return json;
    }, { resource, method, body });
  }
  async function clickSave(button, resource) {
    const waiting = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v1/' + resource && r.request().method() === 'POST');
    await button.click();
    const response = await waiting;
    assert(response.ok(), `Save ${resource} failed: ${await response.text()}`);
    await page.waitForLoadState('networkidle');
    return response.json();
  }
  try {
    await page.goto(base + '/login', { waitUntil: 'networkidle' });
    await page.getByLabel('Email', { exact: true }).fill(env.BOOTSTRAP_ADMIN_EMAIL);
    await page.getByLabel('Password', { exact: true }).fill(env.BOOTSTRAP_ADMIN_PASSWORD);
    await page.getByRole('button', { name: 'Accedi', exact: true }).click();
    await page.waitForURL('**/dashboard');
    assert.equal((await api('rooms/')).count, 0, 'Acceptance test requires an empty disposable database');
    await api('cash/reasons/', 'POST', { name: 'Incasso soggiorno', direction: 'in', is_active: true });
    await api('cash/reasons/', 'POST', { name: 'Versamento di verifica', direction: 'in', is_active: true });
    await api('cash/reasons/', 'POST', { name: 'Rimborso e spesa', direction: 'out', is_active: true });

    await page.goto(base + '/impostazioni', { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: 'Camere e capienze', exact: true }).click();
    await page.getByRole('button', { name: '+ Camera', exact: true }).click();
    await page.locator('#resource-number').fill('101');
    await page.locator('#resource-room_type').fill('Doppia');
    await page.locator('#resource-capacity').fill('2');
    const room = await clickSave(page.getByRole('button', { name: 'Salva', exact: true }), 'rooms/');

    await page.goto(base + '/listino', { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: '+ Tariffa', exact: true }).click();
    await page.locator('#resource-name').fill('Verifica automatica');
    await page.locator('#resource-room_type').fill('Doppia');
    await page.locator('#resource-board').selectOption({ label: 'Solo camera' });
    await page.locator('#resource-start_date').fill(datePart('year') + '-01-01');
    await page.locator('#resource-end_date').fill(String(Number(datePart('year')) + 1) + '-12-31');
    await page.locator('#resource-amount').fill('100');
    await clickSave(page.getByRole('button', { name: 'Salva', exact: true }), 'rates/');

    await page.goto(base + '/cassa', { waitUntil: 'networkidle' });
    await page.getByLabel('Fondo iniziale contanti (€)', { exact: true }).fill('50');
    await clickSave(page.getByRole('button', { name: 'Apri turno', exact: true }), 'cash/shifts/');

    await page.goto(base + '/soggiorni/nuovo', { waitUntil: 'networkidle' });
    await page.locator('select[formcontrolname="room"]').selectOption({ label: '101 · Doppia · max 2' });
    await page.getByLabel('Nome e cognome', { exact: true }).fill('Verifica automatica');
    await page.getByLabel('Arrivo', { exact: true }).fill(day + 'T12:00');
    await page.getByLabel('Partenza', { exact: true }).fill(nextDay + 'T10:00');
    await page.locator('select[formcontrolname="board"]').selectOption('RO');
    await page.getByLabel('Effettua subito il check-in').check();
    await page.getByRole('button', { name: 'Conferma soggiorno', exact: true }).click();
    await page.waitForURL(/\/soggiorni\/\d+$/);
    await page.waitForLoadState('networkidle');
    const id = Number(page.url().split('/').pop());
    let stay = await api(`stays/${id}/`);
    assert.equal(stay.status, 'checked_in');
    assert.equal(Number(stay.total), 100);

    const extraForm = page.locator('form').filter({ has: page.getByRole('button', { name: 'Aggiungi al conto', exact: true }) });
    await extraForm.getByLabel('Descrizione', { exact: true }).fill('Extra libero di verifica');
    await extraForm.getByLabel('Quantità', { exact: true }).fill('2');
    await extraForm.getByLabel('Prezzo unitario (€)', { exact: true }).fill('5');
    await extraForm.locator('[formcontrolname="consumed_at"]').fill(day + 'T08:15');
    await clickSave(page.getByRole('button', { name: 'Aggiungi al conto', exact: true }), `stays/${id}/charges/`);
    assert.equal(Number((await api(`stays/${id}/`)).total), 110);
    const extra = (await api(`stays/${id}/charges/`)).results.find(row => row.kind === 'extra');
    const consumptionClock = new Intl.DateTimeFormat('it-IT', { timeZone: 'Europe/Rome', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(extra.consumed_at));
    assert.equal(consumptionClock, '08:15');
    assert.match(await page.locator('tr').filter({ hasText: 'Extra libero di verifica' }).innerText(), /08:15/);
    const pendingDownload = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Scarica PDF extra', exact: true }).click();
    const statement = await pendingDownload;
    assert.match(statement.suggestedFilename(), /\.pdf$/);
    const pdfPath = await statement.path();
    assert(fs.readFileSync(pdfPath).subarray(0, 5).equals(Buffer.from('%PDF-')), 'Download is not a PDF');
    fs.mkdirSync(path.join(root, '.local/qa'), { recursive: true });
    await statement.saveAs(path.join(root, '.local/qa/extra-workflow.pdf'));
    await page.screenshot({ path: path.join(root, '.local/qa/workflow-extras.png'), fullPage: true });

    async function payment(amount, method) {
      const form = page.locator('app-payment-form');
      await form.getByLabel('Importo (€)', { exact: true }).fill(String(amount));
      await form.locator('select[formcontrolname="method"]').selectOption(method);
      await form.locator('select[formcontrolname="reason"]').selectOption({ label: 'Incasso soggiorno' });
      return clickSave(form.getByRole('button', { name: 'Conferma pagamento', exact: true }), 'payments/');
    }
    await payment(60, 'cash');
    assert.equal(Number((await api(`stays/${id}/`)).balance), 50);
    await page.getByRole('button', { name: 'Effettua check-out', exact: true }).click();
    await clickSave(page.getByRole('button', { name: 'Conferma', exact: true }), `stays/${id}/check-out/`);
    assert.equal((await api(`stays/${id}/`)).status, 'checked_out');
    await payment(50, 'card');
    assert.equal(Number((await api(`stays/${id}/`)).balance), 0);

    await page.locator('app-payment-table tr').filter({ hasText: 'Contanti' }).getByRole('button', { name: 'Rimborsa', exact: true }).click();
    const refundForm = page.locator('app-payment-table form');
    await refundForm.getByLabel('Importo da rimborsare').fill('20');
    await refundForm.locator('select[formcontrolname="reason"]').selectOption({ label: 'Rimborso e spesa' });
    await refundForm.getByLabel('Motivo / Nota').fill('Verifica rimborso parziale');
    const cashPayment = (await api(`payments/?stay=${id}`)).results.find(p => p.method === 'cash' && !p.reverses);
    await clickSave(refundForm.getByRole('button', { name: 'Conferma rimborso', exact: true }), `payments/${cashPayment.id}/refund/`);
    assert.equal(Number((await api(`stays/${id}/`)).balance), 20);

    await page.goto(base + '/cassa', { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: 'Registra entrata', exact: true }).click();
    const incomeForm = page.locator('form').filter({ has: page.getByRole('button', { name: 'Registra entrata', exact: true }) });
    await incomeForm.getByLabel('Importo (€)', { exact: true }).fill('20');
    await incomeForm.locator('select[formcontrolname="reason"]').selectOption({ label: 'Versamento di verifica' });
    await incomeForm.getByLabel('Descrizione', { exact: true }).fill('Reintegro di verifica');
    await clickSave(incomeForm.getByRole('button', { name: 'Registra entrata', exact: true }), 'cash/movements/income/');
    await page.getByRole('button', { name: 'Registra uscita', exact: true }).click();
    const expenseForm = page.locator('form').filter({ has: page.getByRole('button', { name: 'Registra uscita', exact: true }) });
    await expenseForm.getByLabel('Importo (€)', { exact: true }).fill('10');
    await expenseForm.locator('select[formcontrolname="reason"]').selectOption({ label: 'Rimborso e spesa' });
    await expenseForm.getByLabel('Descrizione', { exact: true }).fill('Spesa di verifica');
    await clickSave(expenseForm.getByRole('button', { name: 'Registra uscita', exact: true }), 'cash/movements/');
    const shift = (await api('cash/shifts/')).results[0];
    assert.equal(Number(shift.expected_cash), 100);
    await page.getByLabel('Totale contante fisico contato (€)').fill('98');
    await clickSave(page.getByRole('button', { name: 'Chiudi turno e registra differenza', exact: true }), `cash/shifts/${shift.id}/close/`);
    assert.equal(Number((await api('cash/shifts/')).results[0].difference), -2);

    const report = await api(`reports/?start=${day}&end=${nextDay}`);
    assert.equal(Number(report.income), 130);
    assert.equal(Number(report.expenses), 30);
    assert.equal(Number(report.outstanding), 20);
    assert.equal(report.by_operator_shift[0].movements_count, 5);
    assert.deepEqual(errors, []);
    fs.mkdirSync(path.join(root, '.local/qa'), { recursive: true });
    await page.screenshot({ path: path.join(root, '.local/qa/workflow-cash.png'), fullPage: true });
    console.log(`Browser workflow passed: configurable room ${room.number}, seasonal rate, check-in, timed extra, PDF download, split payment, checkout with debt, later settlement, refund, expense, cash count and report.`);
  } catch (error) {
    fs.mkdirSync(path.join(root, '.local/qa'), { recursive: true });
    await page.screenshot({ path: path.join(root, '.local/qa/workflow-error.png'), fullPage: true });
    throw error;
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
