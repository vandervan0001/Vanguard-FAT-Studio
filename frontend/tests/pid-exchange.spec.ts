import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import type { PidDocument, Project, Snapshot } from '../src/types';

const document: PidDocument = {
  format: 'fat-studio/pid', version: '1.0', title: 'Skid documentaire', source_name: 'skid.pid.json', source_format: 'json', source_sha256: '',
  equipment: [
    { id: 'P101', name: 'P-101', type: 'pump', source_tag: 'P-101', position: { x: 100, y: 100 }, page: 1, confidence: .8, provenance: 'Repère déclaré dans le document', review_required: true },
    { id: 'TK101', name: 'TK-101', type: 'tank', source_tag: 'TK-101', position: { x: 400, y: 100 }, page: 1, confidence: .7, provenance: 'Repère déclaré dans le document', review_required: true },
    { id: 'X101', name: 'X-101', type: 'unknown', source_tag: 'X-101', position: { x: 700, y: 100 }, page: 1, confidence: .2, provenance: 'Type non déterminé', review_required: true },
  ],
  connections: [
    { id: 'c1', source: 'P101', target: 'TK101', label: 'Ligne à vérifier', directed: false, inferred: true, confidence: .4 },
    { id: 'c2', source: 'TK101', target: 'X101', label: '', directed: false, inferred: true, confidence: .2 },
  ],
  pages: [{ number: 1, width: 800, height: 500, image_data_url: '', text: 'P-101 → TK-101 ; X-101 à identifier' }],
  warnings: ['Le sens des liaisons doit être vérifié sur le document source.'], metadata: {},
};

async function mutation(request: APIRequestContext, path: string, body: unknown = {}) {
  const [session, current, state] = await Promise.all([request.get('/api/session'), request.get('/api/project'), request.get('/api/state')]);
  const { token } = await session.json();
  const project: Project = await current.json();
  const snapshot: Snapshot = await state.json();
  return request.post(`/api${path}`, { headers: { 'X-FAT-Token': token, 'X-FAT-Project-ID': project.id, 'X-FAT-Project-Revision': current.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': snapshot.run_id ?? '' }, data: body });
}

test.beforeEach(async ({ request, page }) => {
  expect((await request.get('/api/health')).ok()).toBeTruthy();
  const state: Snapshot = await (await request.get('/api/state')).json();
  if (['running', 'paused', 'error'].includes(state.status)) expect((await mutation(request, '/run/stop')).ok()).toBeTruthy();
  expect((await mutation(request, '/demo/load')).ok()).toBeTruthy();
  await page.goto('/');
  await expect(page.getByLabel('Nom du projet')).toHaveValue('TK-101 · Banc de remplissage');
});

async function openExchange(page: Page) {
  await page.getByRole('button', { name: 'Échanges P&ID', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Échanges P&ID' })).toBeVisible();
}

async function inspect(page: Page) {
  await page.getByLabel('Document P&ID', { exact: true }).setInputFiles({ name: 'skid.pid.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(document)) });
  await expect(page.getByRole('button', { name: 'Inspecter le document', exact: true })).toBeEnabled();
  const upload = page.waitForRequest(request => request.url().includes('/api/pid/inspect?') && request.method() === 'POST');
  await page.getByRole('button', { name: 'Inspecter le document', exact: true }).click();
  const request = await upload;
  expect(await request.headerValue('content-type')).toBe('application/octet-stream');
  expect(new URL(request.url()).searchParams.get('filename')).toBe('skid.pid.json');
  await expect(page.getByRole('heading', { name: 'Revoir l’interprétation', exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByLabel('Type FAT de X-101')).toHaveValue('pid:generic');
}

async function review(page: Page) {
  await page.getByLabel('Type FAT de X-101').selectOption('analog_sensor');
  await page.getByLabel('Conserver la connexion c2', { exact: true }).uncheck();
  await page.getByLabel('Nom du nouveau projet').fill('Skid revu localement');
  await page.getByLabel('J’ai vérifié les équipements sélectionnés', { exact: false }).check();
}

test('revoir puis enregistrer un nouveau P&ID conserve le projet et les essais précédents', async ({ page, request }, testInfo) => {
  const original: Project = await (await request.get('/api/project')).json();
  const initial: Snapshot = await (await request.get('/api/state')).json();
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await openExchange(page);
  expect((await page.getByRole('dialog', { name: 'Échanges P&ID' }).boundingBox())!.width).toBeGreaterThan(1000);
  await inspect(page);
  await expect(page.getByRole('button', { name: 'Préparer le brouillon P&ID', exact: true })).toBeDisabled();
  await review(page);
  await page.getByRole('button', { name: 'Fermer les échanges P&ID', exact: true }).click();
  await openExchange(page);
  await expect(page.getByLabel('Type FAT de X-101')).toHaveValue('analog_sensor');
  await expect(page.getByLabel('Conserver la connexion c2', { exact: true })).not.toBeChecked();
  await expect(page.getByRole('button', { name: 'Inspecter le document', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Préparer le brouillon P&ID', exact: true }).click();
  await expect(page.getByLabel('Brouillon P&ID préparé')).toContainText('3 équipements · 1 connexions');
  await expect(page.getByRole('button', { name: 'Préparer le brouillon P&ID', exact: true })).toHaveCSS('color', 'rgb(255, 255, 255)');
  expect((await (await request.get('/api/project')).json()).id).toBe(original.id);
  await page.screenshot({ path: testInfo.outputPath('pid-review-desktop.png') });
  await page.getByRole('dialog').evaluate(element => { element.scrollTop = 0; });
  await page.screenshot({ path: testInfo.outputPath('pid-review-desktop-top.png') });
  await page.getByLabel('Afficher ce nouveau projet dans l’éditeur.', { exact: false }).check();
  await page.getByRole('button', { name: 'Appliquer au brouillon', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Échanges P&ID' })).not.toBeVisible();
  await expect(page.getByLabel('Nom du projet')).toHaveValue('Skid revu localement');
  await expect(page.getByRole('button', { name: 'Démarrer', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Réinitialiser le modèle', exact: true })).toBeDisabled();
  const unchanged: Project = await (await request.get('/api/project')).json();
  const beforeSave: Snapshot = await (await request.get('/api/state')).json();
  expect(unchanged).toEqual(original);
  expect(beforeSave.run_id).toBe(initial.run_id);
  expect(beforeSave.write_count).toBe(initial.write_count);
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  const saved: Project = await (await request.get('/api/project')).json();
  expect(saved.id).not.toBe(original.id);
  expect(saved.equipment.map(item => item.id)).toEqual(['P101', 'TK101', 'X101']);
  expect(saved.equipment.find(item => item.id === 'X101')?.type).toBe('analog_sensor');
  expect(saved.connections.map(item => item.id)).toEqual(['c1']);
  expect(saved.tags).toEqual([]);
  expect(saved.scenarios).toEqual([]);
  expect(saved.plc.mode).toBe('demo');
  expect(saved.plc.endpoint).toBe('opc.tcp://127.0.0.1:4840');
  expect(saved.plc.approved_virtual_target).toBe('');
  const projects: { id: string }[] = await (await request.get('/api/projects')).json();
  expect(projects.some(item => item.id === original.id)).toBe(true);
  await page.reload();
  await expect(page.getByLabel('Nom du projet')).toHaveValue('Skid revu localement');
  await expect(page.locator('.react-flow__node')).toHaveCount(3);
  await openExchange(page);
  await page.getByRole('button', { name: 'Revoir le document source du projet', exact: true }).click();
  await expect(page.getByLabel('Type FAT de X-101')).toHaveValue('analog_sensor');
  await expect(page.getByRole('heading', { name: 'Revoir l’interprétation', exact: true })).toBeVisible();
  expect(await (await request.get('/api/project')).json()).toEqual(saved);
  expect(errors).toEqual([]);
});

test('un fichier invalide conserve la revue et les brouillons en cours', async ({ page, request }) => {
  const original: Project = await (await request.get('/api/project')).json();
  await page.getByLabel('Nom du projet').fill('Mon brouillon à conserver');
  await openExchange(page);
  await inspect(page);
  await review(page);
  await expect(page.getByRole('button', { name: 'Préparer le brouillon P&ID', exact: true })).toBeDisabled();
  await expect(page.locator('#pid-prepare-blocked')).toContainText('Enregistrez les modifications et observations');
  await page.getByLabel('Document P&ID', { exact: true }).setInputFiles({ name: 'invalide.json', mimeType: 'application/json', buffer: Buffer.from('{') });
  await page.getByRole('button', { name: 'Inspecter le document', exact: true }).click();
  await expect(page.getByRole('alert')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByLabel('Type FAT de X-101')).toHaveValue('analog_sensor');
  await expect(page.getByLabel('Nom du nouveau projet')).toHaveValue('Skid revu localement');
  await page.getByRole('button', { name: 'Exporter le P&ID', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Télécharger PDF', exact: true })).toBeDisabled();
  await expect(page.locator('.pid-export')).toContainText('Enregistrez le projet avant d’exporter');
  await page.getByRole('button', { name: 'Fermer les échanges P&ID', exact: true }).click();
  await expect(page.getByLabel('Nom du projet')).toHaveValue('Mon brouillon à conserver');
  expect(await (await request.get('/api/project')).json()).toEqual(original);
});

test('les exports PDF et SVG utilisent le projet enregistré sans démarrer un essai', async ({ page, request }) => {
  const before: Snapshot = await (await request.get('/api/state')).json();
  await openExchange(page);
  await page.getByRole('button', { name: 'Exporter le P&ID', exact: true }).click();
  for (const [kind, prefix] of [['PDF', '%PDF-'], ['SVG', '<']] as const) {
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: `Télécharger ${kind}`, exact: true }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(new RegExp(`\\.pid\\.${kind.toLowerCase()}$`));
    const file = await download.path();
    expect(file).toBeTruthy();
    const content = await readFile(file!);
    expect(content.toString('utf-8').startsWith(prefix)).toBe(true);
  }
  const after: Snapshot = await (await request.get('/api/state')).json();
  expect(after.project_id).toBe(before.project_id);
  expect(after.project_revision).toBe(before.project_revision);
  expect(after.run_id).toBe(before.run_id);
  expect(after.write_count).toBe(before.write_count);
  expect(after.status).toBe('idle');
});

test('un export dont la révision diffère est refusé avant téléchargement', async ({ page, request }) => {
  const current = await request.get('/api/project');
  const project: Project = await current.json();
  let downloads = 0;
  page.on('download', () => downloads++);
  await page.route('**/api/pid/export/svg', async route => {
    expect(await route.request().headerValue('x-fat-project-id')).toBe(project.id);
    expect(await route.request().headerValue('x-fat-project-revision')).toBe(current.headers()['x-fat-project-revision']);
    await route.fulfill({ status: 200, contentType: 'image/svg+xml', headers: { 'X-FAT-Project-Revision': 'another-revision' }, body: '<svg xmlns="http://www.w3.org/2000/svg" />' });
  });
  await openExchange(page);
  await page.getByRole('button', { name: 'Exporter le P&ID', exact: true }).click();
  await page.getByRole('button', { name: 'Télécharger SVG', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Le projet actif a changé');
  expect(downloads).toBe(0);
});

test('un conflit de projet conserve la revue sans appliquer ni rejouer la préparation', async ({ page, request }) => {
  await openExchange(page);
  await inspect(page);
  await review(page);
  await page.getByRole('button', { name: 'Préparer le brouillon P&ID', exact: true }).click();
  await expect(page.getByLabel('Brouillon P&ID préparé')).toBeVisible();
  const current = await request.get('/api/project');
  const project: Project = await current.json();
  const { token } = await (await request.get('/api/session')).json();
  expect((await request.put('/api/project', { headers: { 'X-FAT-Token': token, 'X-FAT-Project-ID': project.id, 'X-FAT-Project-Revision': current.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': '' }, data: { ...project, name: 'Modification depuis un autre onglet' } })).ok()).toBeTruthy();
  await expect(page.locator('#pid-prepare-blocked')).toContainText('contexte du service local est indisponible');
  await expect(page.getByRole('button', { name: 'Appliquer au brouillon', exact: true })).toBeDisabled();
  await expect(page.getByLabel('Type FAT de X-101')).toHaveValue('analog_sensor');
  await expect(page.getByLabel('Brouillon P&ID préparé')).toBeVisible();
  await page.getByRole('button', { name: 'Fermer les échanges P&ID', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Le projet actif a changé dans un autre onglet');
  await expect(page.getByLabel('Nom du projet')).toHaveValue(project.name);
  const stored: Project = await (await request.get('/api/project')).json();
  expect(stored.name).toBe('Modification depuis un autre onglet');
  expect(stored.equipment).toEqual(project.equipment);
});

test('l’inspection reste possible pendant un essai et l’application attend son arrêt', async ({ page, request }) => {
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  const running: Snapshot = await (await request.get('/api/state')).json();
  await openExchange(page);
  await inspect(page);
  await review(page);
  await expect(page.getByRole('button', { name: 'Préparer le brouillon P&ID', exact: true })).toBeDisabled();
  await expect(page.locator('#pid-prepare-blocked')).toContainText('Arrêtez l’essai');
  const stillRunning: Snapshot = await (await request.get('/api/state')).json();
  expect(stillRunning.status).toBe('running');
  expect(stillRunning.run_id).toBe(running.run_id);
  await page.getByRole('button', { name: 'Fermer les échanges P&ID', exact: true }).click();
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('Arrêté');
  await openExchange(page);
  await expect(page.getByLabel('Type FAT de X-101')).toHaveValue('analog_sensor');
  await expect(page.getByRole('button', { name: 'Préparer le brouillon P&ID', exact: true })).toBeEnabled();
});

test('une inspection lente laisse passer le forçage et l’arrêt avant sa réponse', async ({ page, request }) => {
  let releaseInspection!: () => void;
  let inspectionEntered!: () => void;
  let released = false;
  const pendingInspection = new Promise<void>(resolve => { releaseInspection = () => { released = true; resolve(); }; });
  const inspectionStarted = new Promise<void>(resolve => { inspectionEntered = resolve; });
  await page.route('**/api/pid/inspect?**', async route => {
    inspectionEntered();
    await pendingInspection;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(document) });
  });
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  await openExchange(page);
  await page.getByLabel('Document P&ID', { exact: true }).setInputFiles({ name: 'skid.pid.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(document)) });
  await page.getByRole('button', { name: 'Inspecter le document', exact: true }).click();
  await inspectionStarted;
  let stopped: Snapshot | null = null;
  try {
    await page.getByRole('button', { name: 'Fermer les échanges P&ID', exact: true }).click();
    await page.locator('.react-flow__node[data-id="LT101"]').click();
    await page.getByLabel('Forçage LevelPct', { exact: true }).fill('42');
    const forced = page.waitForResponse(response => new URL(response.url()).pathname === '/api/force/stimulus', { timeout: 6000 });
    await page.locator('.analog-control[data-tag="level"]').getByRole('button', { name: 'Forcer', exact: true }).click();
    expect((await forced).ok()).toBeTruthy();
    expect(released).toBe(false);
    await expect.poll(async () => (await (await request.get('/api/state')).json()).tags.level.forced).toBe(true);
    const stoppedResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/run/stop', { timeout: 6000 });
    await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
    expect((await stoppedResponse).ok()).toBeTruthy();
    expect(released).toBe(false);
    await expect(page.locator('.status-badge')).toHaveText('Arrêté');
    stopped = await (await request.get('/api/state')).json();
  } finally { releaseInspection(); }
  await openExchange(page);
  await expect(page.getByRole('heading', { name: 'Revoir l’interprétation', exact: true })).toBeVisible();
  const after: Snapshot = await (await request.get('/api/state')).json();
  expect(after.status).toBe('stopped');
  expect(after.run_id).toBe(stopped!.run_id);
  expect(after.write_count).toBe(stopped!.write_count);
});

test('le catalogue attribue ses sources et la modale reste accessible sur écran étroit', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Échanges P&ID', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('button', { name: 'Fermer les échanges P&ID', exact: true })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(page.getByRole('dialog').getByRole('button', { name: 'Fermer', exact: true })).toBeFocused();
  await page.getByRole('button', { name: 'Catalogue public', exact: true }).click();
  await expect(page.locator('.pid-source-credit')).toContainText('Scott Duncan');
  await expect(page.locator('.pid-source-credit')).toContainText('CC BY 4.0');
  await expect(page.locator('.pid-public-catalog')).toContainText('ne sont pas des P&ID importables');
  const links = page.locator('.pid-public-catalog a');
  expect(await links.count()).toBeGreaterThan(5);
  for (const link of await links.all()) {
    await expect(link).toHaveAttribute('target', '_blank');
    await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  }
  const box = await page.getByRole('dialog').boundingBox();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  expect(await page.locator('.pid-exchange').evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  await page.getByRole('dialog').evaluate(element => { element.scrollTop = 0; });
  await page.screenshot({ path: testInfo.outputPath('pid-catalog-mobile.png') });
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await expect(page.getByRole('button', { name: 'Échanges P&ID', exact: true })).toBeFocused();
});
