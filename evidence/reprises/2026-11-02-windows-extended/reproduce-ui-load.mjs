import { chromium, expect } from '../frontend/node_modules/@playwright/test/index.mjs';
import { readFile, writeFile } from 'node:fs/promises';
import { performance } from 'node:perf_hooks';

const browser = await chromium.launch({ headless: true });
const output = 'evidence/reprises/2026-11-02-windows-extended';
const errors = [], stateDurations = [], starts = new Map(), pending = [];
const result = { scope: 'Installed ZIP, Chromium, demo mode, HTTP and UI only; no Siemens', equipment: 50, tags: 200,
  shared_load: 'Full Python tests and separate OPC UA endurance checks may run concurrently', started_at_utc: new Date().toISOString() };
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, locale: 'fr-CH' });
  const request = page.request;
  const base = 'http://127.0.0.1:8768';
  const { token } = await (await request.get(base + '/api/session')).json();
  const headers = { 'X-FAT-Token': token };
  let state = await (await request.get(base + '/api/state')).json();
  if (['running', 'paused', 'error'].includes(state.status)) {
    expect((await request.post(base + '/api/run/stop', { headers, data: {} })).ok()).toBeTruthy();
  }
  const project = JSON.parse(await readFile('.local/ui-load-project.json', 'utf8'));
  expect((await request.post(base + '/api/project/import', { headers, data: project })).ok()).toBeTruthy();
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', req => { if (req.url() === base + '/api/state') starts.set(req, performance.now()); });
  page.on('requestfailed', req => { if (!req.failure()?.errorText.includes('ERR_ABORTED')) errors.push(req.failure()?.errorText); });
  page.on('response', response => {
    if (response.url() === base + '/api/state') {
      const work = response.finished().then(() => {
        if (starts.has(response.request())) stateDurations.push(performance.now() - starts.get(response.request()));
        if (!response.ok()) errors.push('state HTTP ' + response.status());
      });
      pending.push(work);
    }
  });
  await page.goto(base, { waitUntil: 'networkidle' });
  await expect(page.locator('.react-flow__node')).toHaveCount(50);
  await page.getByRole('button', { name: 'Centrer le P&ID', exact: true }).first().click();
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  const begin = performance.now();
  await page.waitForTimeout(30_000);
  state = await (await request.get(base + '/api/state')).json();
  expect(state.status).toBe('running');
  expect(Object.keys(state.tags)).toHaveLength(200);
  expect(Object.values(state.tags).every(tag => tag.quality === 'good')).toBeTruthy();
  expect(state.sim_time_s).toBeGreaterThan(20);
  result.running_wall_s = (performance.now() - begin) / 1000;
  result.sim_time_s = state.sim_time_s;
  result.lag_ms_at_capture = state.lag_ms;
  result.write_count = state.write_count;
  await page.screenshot({ path: output + '/ui-load-50x200.png' });
  await page.getByRole('button', { name: 'Mettre en pause', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En pause');
  await page.getByRole('button', { name: /Variables & mapping/ }).click();
  result.rendered_tag_rows = await page.locator('tbody tr').count();
  expect(result.rendered_tag_rows).toBe(200);
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('Arrêté');
  const evidence = await (await request.get(base + '/api/export/json')).json();
  expect(evidence.sample_count).toBe(evidence.samples.length);
  expect(evidence.samples.length).toBeGreaterThan(200);
  expect(evidence.result.verdict).toBe('not_evaluated');
  expect(evidence.samples.every(sample => Object.keys(sample.values).length === 200)).toBeTruthy();
  result.sample_count = evidence.sample_count;
  await Promise.all(pending);
  const timings = stateDurations.sort((a, b) => a - b);
  result.http_state_responses = timings.length;
  result.http_state_response_ms = { p50: timings[Math.floor(timings.length * .5)], p95: timings[Math.floor(timings.length * .95)], max: timings.at(-1) };
  result.browser_errors = errors;
  expect(errors).toEqual([]);
  result.status = 'passed';
} catch (error) {
  result.status = 'failed';
  result.error = String(error.stack || error);
  process.exitCode = 1;
} finally {
  await browser.close();
  result.finished_at_utc = new Date().toISOString();
  await writeFile(output + '/ui-load-50x200.json', JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify(result, null, 2));
}
