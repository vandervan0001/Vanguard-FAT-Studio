import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';
import type { Project, ScenarioPackage, Snapshot } from '../src/types';

async function current(request: APIRequestContext): Promise<Snapshot> { return (await request.get('/api/state')).json(); }
async function change(request: APIRequestContext, path: string, data: unknown = {}) {
  const { token } = await (await request.get('/api/session')).json();
  return request.post(`/api${path}`, { headers: { 'X-FAT-Token': token }, data });
}
async function boot(page: Page) {
  const project: Project = await (await page.request.get('/api/project')).json();
  await page.goto('/');
  await expect(page.getByLabel('Nom du projet')).toHaveValue(project.name);
  return project;
}
async function downloadJSON(page: Page, label: string) {
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: label, exact: true }).click();
  return JSON.parse(await readFile((await (await downloaded).path())!, 'utf8'));
}
function scenarioFile(packaged: unknown) { return { name: 'scenarios.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(packaged)) }; }

test.beforeEach(async ({ request, page }) => {
  if (['running', 'paused', 'error'].includes((await current(request)).status)) expect((await change(request, '/run/stop')).ok()).toBeTruthy();
  expect((await change(request, '/pilot/load')).ok()).toBeTruthy();
  page.on('dialog', dialog => dialog.accept());
});

test('échanger les scénarios versionnés, refuser les collisions et garder le projet physique', async ({ page, request }) => {
  const project = await boot(page);
  await page.getByRole('button', { name: 'Scénarios', exact: true }).click();
  const all: ScenarioPackage = await downloadJSON(page, 'Exporter tous les scénarios');
  expect(all).toMatchObject({ format: 'fat-studio/scenarios', version: '1.0', scenarios: project.scenarios });
  expect(all.tag_contracts.length).toBeGreaterThan(0);
  expect(all.equipment_contracts.length).toBeGreaterThan(0);
  const guided = project.scenarios.find(scenario => scenario.execution_mode === 'guided')!;
  await page.locator('.scenario-list-item').filter({ hasText: guided.name }).click();
  const one: ScenarioPackage = await downloadJSON(page, 'Exporter ce scénario');
  expect(one.scenarios).toEqual([guided]);
  const file = page.getByLabel('Fichier de scénarios JSON', { exact: true });
  const before = await request.get('/api/project');
  const conflict = page.waitForResponse(response => response.url().endsWith('/api/scenarios/import'));
  await file.setInputFiles(scenarioFile(one));
  expect((await conflict).status()).toBe(400);
  expect((await request.get('/api/project')).headers()['x-fat-project-revision']).toBe(before.headers()['x-fat-project-revision']);
  expect(await (await request.get('/api/project')).json()).toEqual(project);
  await page.getByRole('button', { name: 'Fermer le message d’erreur', exact: true }).click();
  const added: ScenarioPackage = { ...one, scenarios: [{ ...guided, id: 'browser-imported-plan', name: 'Plan importé navigateur' }] };
  await file.setInputFiles(scenarioFile(added));
  await expect(page.locator('.scenario-list-item').filter({ hasText: 'Plan importé navigateur' })).toBeVisible();
  const merged: Project = await (await request.get('/api/project')).json();
  expect(merged.scenarios).toHaveLength(project.scenarios.length + 1);
  expect(merged.equipment).toEqual(project.equipment);
  expect(merged.tags).toEqual(project.tags);
  await page.getByLabel('Mode d’import des scénarios').selectOption('replace');
  await page.getByLabel('Fichier de scénarios JSON', { exact: true }).setInputFiles(scenarioFile(one));
  await expect(page.locator('.scenario-list-item')).toHaveCount(2);
  expect((await (await request.get('/api/project')).json()).scenarios).toEqual([guided]);
  await page.locator('.scenario-list-item').filter({ hasText: guided.name }).click();
  await page.getByLabel('Nom du scénario').fill('Après import, contexte à jour');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  const final: Project = await (await request.get('/api/project')).json();
  expect(final.scenarios[0].name).toBe('Après import, contexte à jour');
  const invalid = page.waitForResponse(response => response.url().endsWith('/api/scenarios/import'));
  await page.getByLabel('Fichier de scénarios JSON', { exact: true }).setInputFiles(scenarioFile({ ...one, version: '99.0' }));
  expect((await invalid).status()).toBe(422);
  expect(await (await request.get('/api/project')).json()).toEqual(final);
});

test('la pause ouvre le builder, reprendre conserve le run, appliquer préserve son historique', async ({ page, request }) => {
  const project = await boot(page);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect.poll(async () => (await current(request)).sim_time_s).toBeGreaterThan(.5);
  const originalRun = (await current(request)).run_id!;
  await page.getByRole('button', { name: 'Mettre en pause', exact: true }).click();
  await expect(page.locator('.palette')).toBeVisible();
  await expect(page.locator('.react-flow__node')).toHaveCount(project.equipment.length);
  await page.getByRole('button', { name: 'Reprendre', exact: true }).click();
  await expect(page.getByLabel('Entrées digitales', { exact: true })).toBeVisible();
  expect((await current(request)).run_id).toBe(originalRun);
  await page.getByRole('button', { name: 'Mettre en pause', exact: true }).click();
  await page.locator('.react-flow__node[data-id="P101"]').click();
  await page.getByLabel('Nom / repère', { exact: true }).fill('P-101 · Repère édité en pause');
  await expect(page.getByRole('button', { name: 'Reprendre', exact: true })).toBeDisabled();
  await page.locator('.project-actions').getByRole('button', { name: 'Appliquer en pause', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('Prêt');
  expect((await current(request)).run_id).toBeNull();
  const archive = await (await request.get(`/api/runs/${originalRun}/json`)).json();
  expect(archive.status).toBe('stopped');
  expect(archive.project.equipment).toEqual(project.equipment);
  expect(archive.samples.length).toBeGreaterThan(0);
  expect(archive.result.verdict).toBe('not_evaluated');
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  expect((await current(request)).run_id).not.toBe(originalRun);
  await expect(page.locator('.react-flow__node[data-id="P101"]')).toContainText('Repère édité en pause');
});

test('archiver puis restaurer dans un nouveau dossier conserve les preuves et refuse un ancien onglet', async ({ page, context, request }, testInfo) => {
  const project = await boot(page);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect.poll(async () => (await current(request)).sim_time_s).toBeGreaterThan(.3);
  const runId = (await current(request)).run_id!;
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('Arrêté');
  await page.getByRole('button', { name: 'Réinitialiser le modèle', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('Prêt');
  expect((await current(request)).run_id).toBeNull();
  const originalWorkspace = await (await request.get('/api/workspace')).json();
  const originalResponse = await request.get('/api/project');
  const originalRevision = originalResponse.headers()['x-fat-project-revision'];
  const proof = await (await request.get(`/api/runs/${runId}/json`)).json();
  const stale = await context.newPage();
  try {
    await boot(stale);
    const retained = await current(request);
    await stale.route('**/api/state', route => route.fulfill({ json: retained }));
    await stale.getByLabel('Nom du projet').fill('Brouillon de l’espace original');
    await page.getByRole('button', { name: 'Ouvrir', exact: true }).click();
    const invalid = page.waitForResponse(response => response.url().endsWith('/api/project/archive/import'));
    await page.getByLabel('Archive FAT à restaurer', { exact: true }).setInputFiles({ name: 'invalide.fat.zip', mimeType: 'application/zip', buffer: Buffer.from('Ce fichier ne contient pas une archive ZIP.') });
    expect((await invalid).status()).toBe(400);
    await expect(page.getByRole('dialog').getByRole('alert')).toBeVisible();
    await page.getByRole('dialog').screenshot({ path: testInfo.outputPath('public-archive-invalid.png'), style: '.statusbar,.toast { visibility: hidden !important; }' });
    expect((await (await request.get('/api/workspace')).json()).id).toBe(originalWorkspace.id);
    expect((await request.get('/api/project')).headers()['x-fat-project-revision']).toBe(originalRevision);
    await page.getByRole('dialog').getByRole('button', { name: 'Fermer le message d’erreur', exact: true }).click();
    const downloaded = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Exporter l’archive FAT', exact: true }).click();
    const archive = await downloaded;
    expect(archive.suggestedFilename()).toMatch(/\.fat\.zip$/);
    const bytes = await readFile((await archive.path())!);
    expect(Array.from(bytes.subarray(0, 4))).toEqual([80, 75, 3, 4]);
    await page.getByLabel('Archive FAT à restaurer', { exact: true }).setInputFiles({ name: archive.suggestedFilename(), mimeType: 'application/zip', buffer: bytes });
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByRole('status')).toContainText('nouveau dossier');
    const restoredWorkspace = await (await request.get('/api/workspace')).json();
    expect(restoredWorkspace.id).not.toBe(originalWorkspace.id);
    expect(restoredWorkspace.path).not.toBe(originalWorkspace.path);
    const restored = await request.get('/api/project');
    const restoredProject: Project = await restored.json();
    expect(restoredProject.id).toBe(project.id);
    expect(restoredProject.equipment).toEqual(project.equipment);
    expect(restoredProject.tags).toEqual(project.tags);
    expect(restoredProject.scenarios).toEqual(project.scenarios);
    expect(restored.headers()['x-fat-project-revision']).not.toBe(originalRevision);
    expect((await current(request)).run_id).toBeNull();
    expect((await current(request)).status).toBe('idle');
    const restoredProof = await (await request.get(`/api/runs/${runId}/json`)).json();
    expect(restoredProof.samples).toEqual(proof.samples);
    expect(restoredProof.result).toEqual(proof.result);
    expect(restoredProof.project).toEqual(proof.project);
    const rejected = stale.waitForResponse(response => response.url().endsWith('/api/project') && response.request().method() === 'PUT');
    await stale.getByRole('button', { name: 'Enregistrer', exact: true }).click();
    expect((await rejected).status()).toBe(409);
    await expect(stale.getByLabel('Nom du projet')).toHaveValue('Brouillon de l’espace original');
    await stale.getByRole('button', { name: 'Fermer le message d’erreur', exact: true }).click();
    await stale.getByRole('button', { name: 'Tendances & rapport', exact: true }).click();
    await stale.getByRole('button', { name: 'Historique', exact: true }).click();
    const staleDownloads: string[] = []; stale.on('download', file => staleDownloads.push(file.suggestedFilename()));
    const rejectedExport = Promise.race([
      stale.waitForResponse(response => response.url().endsWith(`/api/runs/${runId}/json`)).then(response => ({ kind: 'response', status: response.status() })),
      stale.waitForEvent('download').then(file => ({ kind: 'download', filename: file.suggestedFilename() })),
    ]);
    await stale.locator('.saved-run').first().getByRole('button', { name: 'JSON', exact: true }).click();
    expect(await rejectedExport).toEqual({ kind: 'response', status: 409 });
    await expect(stale.getByRole('dialog')).toHaveCount(0);
    await expect(stale.getByRole('alert')).toContainText('autre onglet');
    expect(staleDownloads).toEqual([]);
    expect((await (await request.get('/api/project')).json()).name).toBe(project.name);
    expect((await request.get('/api/project')).headers()['x-fat-project-revision']).toBe(restored.headers()['x-fat-project-revision']);
    await page.getByRole('button', { name: 'Ouvrir', exact: true }).click();
    await expect(page.locator('.workspace-item')).toHaveCount(2);
    await expect(page.locator(`.workspace-item[data-workspace="${restoredWorkspace.id}"]`)).toContainText(restoredWorkspace.path);
    await page.getByRole('dialog').screenshot({ path: testInfo.outputPath('public-archive-workspaces.png'), style: '.statusbar,.toast { visibility: hidden !important; }' });
    await page.locator(`.workspace-item[data-workspace="${originalWorkspace.id}"]`).getByRole('button').click();
    await expect(page.getByRole('status')).toContainText('Dossier FAT ouvert');
    expect((await (await request.get('/api/workspace')).json()).id).toBe(originalWorkspace.id);
    expect((await (await request.get(`/api/runs/${runId}/json`)).json()).samples).toEqual(proof.samples);
  } finally { await stale.close(); }
});

test('animer un objet par TRUE ou FALSE et rendre une qualité invalide visible', async ({ page, request }, testInfo) => {
  await boot(page);
  await page.getByRole('button', { name: 'Construire', exact: true }).click();
  await page.locator('.react-flow__node[data-id="P101"]').click();
  await page.getByLabel('Lier l’apparence à un tag', { exact: true }).check();
  await page.getByLabel('Variable d’animation', { exact: true }).selectOption('p101_command');
  await page.getByLabel('Valeur active de l’animation', { exact: true }).selectOption('false');
  await page.getByLabel('Effet visuel', { exact: true }).selectOption('pulse');
  await page.locator('.react-flow__node[data-id="TK101"]').click();
  await page.getByLabel('Variable d’animation', { exact: true }).selectOption('lt101_raw');
  await page.getByLabel('Effet visuel', { exact: true }).selectOption('level');
  await page.getByLabel('Animation minimum', { exact: true }).fill('0');
  await page.getByLabel('Animation maximum', { exact: true }).fill('27648');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  const project: Project = await (await request.get('/api/project')).json();
  expect(project.equipment.find(item => item.id === 'P101')!.animation).toMatchObject({ tag_id: 'p101_command', value: false, effect: 'pulse' });
  const writes: string[] = [];
  page.on('request', request => { if (request.method() === 'POST' && /\/api\/force/.test(request.url())) writes.push(request.postDataJSON().tag_id); });
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  const level = page.locator('.analog-control[data-tag="lt101_raw"]');
  await level.getByLabel('Unité de stimulus LT101_Raw').selectOption('percent');
  await level.getByLabel('Forçage LT101_Raw').fill('50');
  await level.getByRole('button', { name: 'Forcer', exact: true }).click();
  await expect.poll(async () => Number(await page.locator('.react-flow__node[data-id="TK101"] .tank-liquid').getAttribute('height'))).toBeCloseTo(28.5, 6);
  const pump = page.locator('.react-flow__node[data-id="P101"] .equipment-node');
  await expect(pump).toHaveAttribute('data-animation-active', 'true');
  await expect(pump).toHaveClass(/animation-pulse/);
  await page.locator('.digital-control[data-tag="p101_request"] .digital-push').dblclick();
  await expect.poll(async () => (await current(request)).tags.p101_command.value).toBe(true);
  await expect(pump).toHaveAttribute('data-animation-active', 'false');
  await page.locator('.digital-control[data-tag="p101_request"] .release-contact').click();
  await expect(pump).toHaveAttribute('data-animation-active', 'true');
  await page.route('**/api/state', async route => {
    const response = await route.fetch(); const snapshot: Snapshot = await response.json();
    snapshot.tags.p101_command.quality = 'bad';
    await route.fulfill({ response, json: snapshot });
  });
  await expect(pump).toHaveAttribute('data-animation-quality', 'unavailable');
  await expect(pump).toHaveAttribute('data-animation-active', 'false');
  await expect(pump).not.toHaveClass(/animation-pulse/);
  await expect(pump).toContainText('Indisponible');
  await pump.screenshot({ path: testInfo.outputPath('public-animation-bad-quality.png') });
  await page.unroute('**/api/state');
  await expect(pump).toHaveAttribute('data-animation-active', 'true');
  expect(writes).toEqual(['lt101_raw', 'p101_request']);
});

test('le flux dessiné suit le débit du modèle, y compris vanne fermée et défaut moteur', async ({ page, request }) => {
  await boot(page);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  const pipe = page.locator('.pipe-core[data-edge-id="pipe_0"]');
  await page.locator('.digital-control[data-tag="p101_request"] .digital-push').dblclick();
  await expect.poll(async () => (await current(request)).tags.p101_running.value).toBe(true);
  expect((await current(request)).equipment.P101.flow_l_s).toBe(0);
  await expect(pipe).toHaveAttribute('data-flowing', 'false');
  await page.locator('.digital-control[data-tag="xv101_request"] .digital-push').dblclick();
  await expect.poll(async () => Number((await current(request)).equipment.P101.flow_l_s)).toBeGreaterThan(0);
  await expect(pipe).toHaveAttribute('data-flowing', 'true');
  await page.locator('.react-flow__node[data-id="P101"]').click();
  await page.getByRole('button', { name: 'Injecter', exact: true }).click();
  await expect.poll(async () => (await current(request)).tags.p101_fault.value).toBe(true);
  await expect(pipe).toHaveAttribute('data-flowing', 'false');
});

test('une animation numérique REAL compare le seuil au Float32 réellement échangé', async ({ page, request }) => {
  await boot(page);
  await page.getByRole('button', { name: 'Construire', exact: true }).click();
  await page.locator('.react-flow__node[data-id="P101"]').click();
  await page.getByLabel('Variable d’animation', { exact: true }).selectOption('p101_speed_command');
  await page.getByLabel('Opérateur d’animation', { exact: true }).selectOption('eq');
  await page.getByLabel('Valeur active de l’animation', { exact: true }).fill('0.1');
  await page.getByLabel('Effet visuel', { exact: true }).selectOption('highlight');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  const speed = page.locator('.analog-control[data-tag="p101_requested_speed"]');
  await speed.getByLabel('Forçage P101_RequestedSpeed').fill('0.1');
  await speed.getByRole('button', { name: 'Forcer', exact: true }).click();
  await page.locator('.digital-control[data-tag="p101_request"] .digital-push').dblclick();
  await expect.poll(async () => (await current(request)).tags.p101_speed_command.value).toBe(Math.fround(.1));
  await expect(page.locator('.react-flow__node[data-id="P101"] .equipment-node')).toHaveAttribute('data-animation-active', 'true');
  expect((await (await request.get('/api/project')).json()).equipment.find((item: { id: string }) => item.id === 'P101').animation.value).toBe(.1);
});

test('P&ID et pupitres restent dans la page à 768, 920, 1024 et 1280 pixels', async ({ page }, testInfo) => {
  await boot(page);
  await expect(page.locator('.equipment-node.quality-unavailable')).toHaveCount(0);
  const geometries = [];
  for (const width of [768, 920, 1024, 1280]) {
    await page.setViewportSize({ width, height: 960 });
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const digital = (await page.getByLabel('Entrées digitales', { exact: true }).boundingBox())!;
    const analog = (await page.getByLabel('Entrées analogiques', { exact: true }).boundingBox())!;
    const canvas = (await page.locator('.canvas-area').boundingBox())!;
    expect(digital.x).toBeGreaterThanOrEqual(0); expect(analog.x + analog.width).toBeLessThanOrEqual(width + 1);
    expect(digital.x + digital.width).toBeLessThanOrEqual(analog.x + 1);
    expect(canvas.height).toBeGreaterThanOrEqual(500);
    await page.locator('.react-flow__node[data-id="TK101"]').click();
    const inspector = (await page.locator('.canvas-area > .inspector').boundingBox())!;
    expect(inspector.x).toBeGreaterThanOrEqual(canvas.x);
    expect(inspector.x + inspector.width).toBeLessThanOrEqual(canvas.x + canvas.width + 1);
    const afterAnalog = (await page.getByLabel('Entrées analogiques', { exact: true }).boundingBox())!;
    const afterCanvas = (await page.locator('.canvas-area').boundingBox())!;
    expect({ ...afterAnalog, y: afterAnalog.y - afterCanvas.y }).toEqual({ ...analog, y: analog.y - canvas.y });
    await page.getByRole('button', { name: 'Fermer les propriétés', exact: true }).click();
    await page.waitForTimeout(400); // Wait for the responsive FitView transition before recording the rendering.
    await page.screenshot({ path: testInfo.outputPath(`public-workbench-${width}.png`), fullPage: true, style: '.statusbar,.toast { visibility: hidden !important; }' });
    geometries.push({ width, digital, analog, canvas, inspector });
  }
  await page.getByRole('button', { name: 'Mode présentation', exact: true }).click();
  await expect(page.getByLabel('Entrées digitales', { exact: true })).toBeHidden();
  await expect(page.locator('.canvas-area')).toHaveCSS('width', '1280px');
  await page.waitForTimeout(500); // Record the presentation after its FitView transition.
  await expect(page.getByRole('button', { name: 'Arrêter l’essai', exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('public-presentation-1280.png'), fullPage: true, style: '.statusbar,.toast { visibility: hidden !important; }' });
  await page.getByRole('button', { name: 'Afficher les pupitres', exact: true }).click();
  await expect(page.getByLabel('Entrées analogiques', { exact: true })).toBeVisible();
  await writeFile(testInfo.outputPath('responsive-geometry.json'), JSON.stringify(geometries, null, 2));
});
