import { expect, test, type APIRequestContext } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
import type { Project, Snapshot } from '../src/types';

async function state(request: APIRequestContext): Promise<Snapshot> { return (await request.get('/api/state')).json(); }
async function change(request: APIRequestContext, path: string) {
  const session = await (await request.get('/api/session')).json();
  return request.post(`/api${path}`, { headers: { 'X-FAT-Token': session.token }, data: {} });
}

test('audit public : échelles déclarées, préréglages et préparation des vues FAT', async ({ page, request }, testInfo) => {
  if (['running', 'paused', 'error'].includes((await state(request)).status)) expect((await change(request, '/run/stop')).ok()).toBeTruthy();
  expect((await change(request, '/pilot/load')).ok()).toBeTruthy();
  const project: Project = await (await request.get('/api/project')).json();
  expect(project.tags.every(tag => !tag.node_id && !tag.plc_address)).toBe(true);
  expect(project.scenarios.filter(scenario => scenario.execution_mode === 'timed')).toHaveLength(8);
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('dialog', dialog => dialog.accept());
  await page.goto('/');
  await expect(page.getByLabel('Nom du projet')).toHaveValue(project.name);
  const digitalBox = (await page.getByLabel('Entrées digitales', { exact: true }).boundingBox())!;
  const canvasBox = (await page.locator('.canvas-area').boundingBox())!;
  const analogBox = (await page.getByLabel('Entrées analogiques', { exact: true }).boundingBox())!;
  expect(digitalBox.x + digitalBox.width).toBeLessThanOrEqual(canvasBox.x + 1);
  expect(analogBox.x).toBeGreaterThanOrEqual(canvasBox.x + canvasBox.width - 1);
  await page.getByRole('button', { name: /^Variables & mapping/ }).click();
  const tag = project.tags.find(tag => tag.id === 'lt201_raw')!;
  const row = page.locator('.tags-table tbody > tr').filter({ has: page.getByRole('button', { name: new RegExp(`^${tag.name}`) }) });
  await expect(row.locator('.plc-address-cell')).toContainText('À renseigner');
  await expect(row.locator('.node-id')).toContainText('À découvrir');
  await page.getByRole('button', { name: new RegExp(`^${tag.name}`) }).click();
  const details = page.locator('.tag-details');
  await details.getByLabel(`Conversion analogique ${tag.name}`, { exact: true }).selectOption('0-10V');
  await details.getByLabel('Minimum ingénierie', { exact: true }).fill('10');
  await details.getByLabel('Maximum ingénierie', { exact: true }).fill('30');
  await details.getByLabel('Unité ingénierie', { exact: true }).fill('°C');
  await page.getByRole('button', { name: 'Scénarios', exact: true }).click();
  const scenario = project.scenarios.find(scenario => scenario.id === 'demo-stop')!;
  await page.locator('.scenario-list-item').filter({ hasText: scenario.name }).click();
  await page.getByText('Vue et courbes à préparer', { exact: true }).click();
  const focus = page.getByRole('group', { name: 'Équipements à cadrer', exact: true });
  while (await focus.locator('input:checked').count()) await focus.locator('input:checked').first().uncheck();
  await focus.getByLabel(project.equipment.find(item => item.id === 'TK101')!.name, { exact: true }).check();
  const trends = page.getByRole('group', { name: 'Variables à tracer (8 maximum)', exact: true });
  while (await trends.locator('input:checked').count()) await trends.locator('input:checked').first().uncheck();
  await trends.getByLabel(project.tags.find(tag => tag.id === 'lt101_raw')!.name, { exact: true }).check();
  await trends.getByLabel(project.tags.find(tag => tag.id === 'stop_healthy')!.name, { exact: true }).check();
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  const saved: Project = await (await request.get('/api/project')).json();
  expect(saved.tags.find(item => item.id === 'lt201_raw')!.signal).toMatchObject({ engineering_min: 10, engineering_max: 30, engineering_unit: '°C' });
  expect(saved.scenarios.find(item => item.id === scenario.id)).toMatchObject({ focus_equipment: ['TK101'], trend_tags: ['lt101_raw', 'stop_healthy'] });
  await page.getByRole('button', { name: 'P&ID', exact: true }).click();
  await page.getByRole('button', { name: 'Préparer la vue', exact: true }).click();
  await expect(page.locator('.equipment-node.fat-focus')).toHaveCount(1);
  await expect(page.locator('.live-overview .recharts-legend-wrapper')).toContainText('LT101_Raw');
  await expect(page.locator('.live-overview .recharts-legend-wrapper')).toContainText('StopHealthy');
  await page.getByLabel('Scénario', { exact: true }).selectOption('');
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  const input = page.locator('.analog-control[data-tag="lt201_raw"]');
  const unit = input.getByLabel(`Unité de stimulus ${tag.name}`);
  const value = input.getByLabel(`Forçage ${tag.name}`);
  const measurements: Record<string, unknown>[] = [];
  for (const stimulus of [{ unit: 'V', value: 5, raw: 13824 }, { unit: 'engineering', value: 25, raw: 20736 }, { unit: 'percent', value: 50, raw: 13824 }, { unit: 'native', value: 6912, raw: 6912 }]) {
    await unit.selectOption(stimulus.unit); await value.fill(String(stimulus.value));
    await input.getByRole('button', { name: /^(Forcer|Modifier)$/ }).click();
    await expect.poll(async () => (await state(request)).tags.lt201_raw.value).toBe(stimulus.raw);
    measurements.push({ ...stimulus, observed: (await state(request)).tags.lt201_raw });
  }
  await expect(input.locator('.analog-reading')).toContainText('15');
  await expect(input.locator('.analog-reading')).toContainText('°C');
  for (const [percent, raw] of [[0, 0], [25, 6912], [50, 13824], [100, 27648]]) {
    await input.getByRole('button', { name: `Préparer ${percent} % ${tag.name}`, exact: true }).click();
    await expect(value).toHaveValue(String(raw));
    await input.getByRole('button', { name: 'Modifier', exact: true }).click();
    await expect.poll(async () => (await state(request)).tags.lt201_raw.value).toBe(raw);
  }
  await input.screenshot({ path: testInfo.outputPath('public-custom-engineering.png') });
  await input.getByRole('button', { name: `Libérer ${tag.name}`, exact: true }).click();
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
  expect((await state(request)).result.verdict).toBe('not_evaluated');
  expect(errors).toEqual([]);
  await writeFile(testInfo.outputPath('ui-observations.json'), JSON.stringify({ mode: 'temporary local demonstration only', tag_count: project.tags.length, geometry: { digitalBox, canvasBox, analogBox }, measurements, browser_errors: errors }, null, 2));
});
