import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import type { PidDocument, Project, Snapshot } from '../src/types';

async function mutation(request: APIRequestContext, path: string, data: unknown = {}) {
  const [session, current, state] = await Promise.all([request.get('/api/session'), request.get('/api/project'), request.get('/api/state')]);
  const { token } = await session.json();
  const project: Project = await current.json();
  const snapshot: Snapshot = await state.json();
  return request.post(`/api${path}`, { data, headers: { 'X-FAT-Token': token, 'X-FAT-Project-ID': project.id, 'X-FAT-Project-Revision': current.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': snapshot.run_id ?? '' } });
}

test.beforeEach(async ({ request, page }) => {
  expect((await request.get('/api/health')).ok()).toBe(true);
  if (['running', 'paused', 'error'].includes((await (await request.get('/api/state')).json()).status)) expect((await mutation(request, '/run/stop')).ok()).toBe(true);
  expect((await mutation(request, '/demo/load')).ok()).toBe(true);
  await page.goto('/');
  await expect(page.getByLabel('Nom du projet')).toHaveValue('TK-101 · Banc de remplissage');
});

async function save(page: Page) {
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
}

async function connect(page: Page, source: Locator, target: Locator) {
  const start = await source.boundingBox(), end = await target.boundingBox();
  expect(start).not.toBeNull(); expect(end).not.toBeNull();
  await page.mouse.move(start!.x + start!.width / 2, start!.y + start!.height / 2);
  await page.mouse.down();
  await page.mouse.move(end!.x + end!.width / 2, end!.y + end!.height / 2, { steps: 20 });
  await page.mouse.up();
}

const source: PidDocument = {
  format: 'fat-studio/pid', version: '1.0', title: 'Échangeur et vanne à trois voies', source_name: 'rich.pid.json', source_format: 'json', source_sha256: '', pages: [], warnings: [], metadata: {},
  equipment: [
    { id: 'E101', name: 'E-101', type: 'heat_exchanger', documentary: true, source_kind: 'ShellAndTubeHeatExchanger', rotation: 90, source_tag: 'E-101', position: { x: 100, y: 100 }, page: 1, confidence: 1, provenance: 'Fixture documentaire déclarée', review_required: true },
    { id: 'V101', name: 'V-101', type: 'three_way_valve', documentary: true, source_kind: 'ThreeWayValve', rotation: 0, source_tag: 'V-101', position: { x: 500, y: 100 }, page: 1, confidence: 1, provenance: 'Fixture documentaire déclarée', review_required: true },
    { id: 'X101', name: 'X-101', type: 'VendorWidget', source_kind: 'VendorWidget', rotation: 0, source_tag: 'X-101', position: { x: 500, y: 400 }, page: 1, confidence: .2, provenance: 'Type fournisseur à conserver', review_required: true },
    { id: 'T101', name: 'TK-DOC', type: 'tank', documentary: true, source_kind: 'TankDrawingOnly', rotation: 0, source_tag: 'TK-DOC', position: { x: 100, y: 400 }, page: 1, confidence: 1, provenance: 'Dessin sans modèle physique', review_required: true },
  ],
  connections: [
    { id: 'primary', source: 'E101', source_port: 'primary_out', target: 'V101', target_port: 'AB', label: 'Primaire', directed: true, inferred: false, confidence: 1 },
    { id: 'secondary', source: 'E101', source_port: 'secondary_out', target: 'V101', target_port: 'A', label: 'Secondaire distinct', directed: true, inferred: false, confidence: 1 },
  ],
};

async function inspect(page: Page, document = source) {
  await page.getByRole('button', { name: 'Échanges P&ID', exact: true }).click();
  await page.getByRole('button', { name: 'Importer et revoir', exact: true }).click();
  await page.getByLabel('Document P&ID', { exact: true }).setInputFiles({ name: 'rich.pid.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(document)) });
  await page.getByRole('button', { name: 'Inspecter le document', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Revoir l’interprétation', exact: true })).toBeVisible({ timeout: 30_000 });
}

async function apply(page: Page) {
  await page.getByLabel('J’ai vérifié les équipements sélectionnés', { exact: false }).check();
  await page.getByRole('button', { name: 'Préparer le brouillon P&ID', exact: true }).click();
  await expect(page.getByLabel('Brouillon P&ID préparé')).toBeVisible();
  await page.getByLabel('Afficher ce nouveau projet dans l’éditeur.', { exact: false }).check();
  await page.getByRole('button', { name: 'Appliquer au brouillon', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Échanges P&ID' })).not.toBeVisible();
}

test('la bibliothèque ajoute échangeur et vanne 3 voies, raccorde les piquages et conserve la rotation', async ({ page, request }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.getByRole('button', { name: 'Nouveau', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Nom du projet').fill('Bibliothèque documentaire');
  await page.getByRole('button', { name: 'Créer le projet', exact: true }).click();
  await expect(page.locator('.react-flow__node')).toHaveCount(0);
  await expect(page.getByRole('region', { name: 'Symboles P&ID documentaires' })).toBeVisible();
  expect(await page.locator('.pid-symbol-palette-item').count()).toBe(61);
  await expect(page.getByRole('button', { name: 'Ajouter Pompe, représentation générale', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Ajouter Transmetteur de débit (FT)', exact: true })).toBeVisible();
  const search = page.getByLabel('Rechercher dans la bibliothèque');
  await search.fill('calandre');
  await page.getByRole('button', { name: 'Ajouter Échangeur à calandre et tubes', exact: true }).dragTo(page.locator('.canvas-area'), { targetPosition: { x: 150, y: 200 } });
  await expect(page.getByLabel('Nom / repère')).toHaveValue('E-101');
  await expect(page.getByLabel('Symbole documentaire', { exact: true })).toContainText('Non simulé');
  await expect(page.getByRole('button', { name: 'Créer les tags manquants', exact: true })).toHaveCount(0);
  await page.getByLabel('Rotation du symbole').selectOption('90');
  const hx = page.locator('.react-flow__node').filter({ has: page.locator('[data-symbol-kind="heat_exchanger"]') });
  await expect(hx.locator('[data-port-id]')).toHaveCount(4);
  await expect(hx.locator('.pid-symbol-body')).toHaveAttribute('data-rotation', '90');
  await search.fill('3 voies');
  await page.getByRole('button', { name: 'Ajouter Vanne trois voies', exact: true }).dragTo(page.locator('.canvas-area'), { targetPosition: { x: 520, y: 200 } });
  const valve = page.locator('.react-flow__node').filter({ has: page.locator('[data-symbol-kind="three_way_valve"]') });
  await expect(valve.locator('[data-port-id]')).toHaveCount(3);
  // The first fit zooms a single item; place the second symbol clear of it using a real drag.
  const label = await hx.locator('.node-label').boundingBox();
  await page.mouse.move(label!.x + label!.width / 2, label!.y + label!.height / 2);
  await page.mouse.down();
  await page.mouse.move(label!.x + label!.width / 2 - 220, label!.y + label!.height / 2, { steps: 15 });
  await page.mouse.up();
  await connect(page, hx.locator('[data-port-id="primary_out"]'), valve.locator('[data-port-id="AB"]'));
  await expect(page.locator('.react-flow__edge')).toHaveCount(1);
  await connect(page, hx.locator('[data-port-id="secondary_out"]'), valve.locator('[data-port-id="A"]'));
  await expect(page.locator('.react-flow__edge')).toHaveCount(2);
  await save(page);
  const stored: Project = await (await request.get('/api/project')).json();
  expect(stored.tags).toEqual([]);
  expect(stored.equipment.map(item => item.type)).toEqual(['pid_symbol', 'pid_symbol']);
  expect(stored.equipment[0].symbol_kind).toBe('heat_exchanger');
  expect(stored.equipment[0].rotation).toBe(90);
  expect(stored.connections.map(item => [item.source_port, item.target_port])).toEqual([['primary_out', 'AB'], ['secondary_out', 'A']]);
  await page.screenshot({ path: testInfo.outputPath('library-hx-three-way-desktop.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: testInfo.outputPath('library-hx-three-way-mobile.png'), fullPage: true });
  expect(await page.locator('.workbench').evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.reload();
  await expect(page.locator('.type-pid_symbol .node-value')).toHaveText(['Non simulé', 'Non simulé']);
  await expect(page.locator('.react-flow__edge')).toHaveCount(2);
  expect((await (await request.get('/api/project')).json()).connections).toEqual(stored.connections);
  expect(errors).toEqual([]);
});

test('la revue préserve les symboles inconnus, les deux circuits et les objets purement documentaires après export', async ({ page, request }, testInfo) => {
  const original: Project = await (await request.get('/api/project')).json();
  await inspect(page);
  await expect(page.getByLabel('Type FAT de E-101')).toHaveValue('pid:heat_exchanger');
  await expect(page.getByLabel('Type FAT de V-101')).toHaveValue('pid:three_way_valve');
  await expect(page.getByLabel('Type FAT de X-101')).toHaveValue('pid:generic');
  await expect(page.getByLabel('Type FAT de TK-DOC')).toHaveValue('pid:tank');
  await apply(page);
  await save(page);
  const stored: Project = await (await request.get('/api/project')).json();
  expect(stored.equipment).toHaveLength(4);
  expect(stored.equipment.every(item => item.type === 'pid_symbol')).toBe(true);
  expect(stored.equipment.find(item => item.id === 'X101')).toMatchObject({ symbol_kind: 'generic', source_kind: 'VendorWidget' });
  expect(stored.connections.map(item => [item.source_port, item.target_port])).toEqual([['primary_out', 'AB'], ['secondary_out', 'A']]);
  expect(stored.tags).toEqual([]);
  expect((await (await request.get('/api/projects')).json()).some((item: Project) => item.id === original.id)).toBe(true);
  await page.reload();
  await page.locator('.react-flow__node[data-id="E101"]').click();
  await expect(page.getByLabel('Symbole documentaire', { exact: true })).toContainText('circuits primaire et secondaire restent distincts');
  await page.screenshot({ path: testInfo.outputPath('source-hx-circuits-desktop.png') });
  await page.getByRole('button', { name: 'Échanges P&ID', exact: true }).click();
  await page.getByRole('button', { name: 'Exporter le P&ID', exact: true }).click();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Télécharger JSON', exact: true }).click();
  const exported: PidDocument = JSON.parse(await readFile((await (await download).path())!, 'utf8'));
  expect(exported.equipment.every(item => item.documentary)).toBe(true);
  expect(exported.equipment.find(item => item.id === 'E101')).toMatchObject({ type: 'heat_exchanger', rotation: 90 });
  expect(exported.equipment.find(item => item.id === 'T101')).toMatchObject({ type: 'tank', documentary: true });
  expect(exported.connections.map(item => [item.source_port, item.target_port])).toEqual([['primary_out', 'AB'], ['secondary_out', 'A']]);
  await page.getByRole('button', { name: 'Fermer les échanges P&ID', exact: true }).click();
  await inspect(page, exported);
  await expect(page.getByLabel('Type FAT de TK-DOC')).toHaveValue('pid:tank');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('dialog').evaluate(element => { element.scrollTop = 0; });
  await page.screenshot({ path: testInfo.outputPath('source-review-mobile.png') });
  expect(await page.locator('.pid-exchange').evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
});

test('un piquage fournisseur non positionné reste visible à la revue et se corrige explicitement', async ({ page, request }) => {
  const foreign = structuredClone(source);
  foreign.connections[0].target_port = 'supplier_nozzle';
  await inspect(page, foreign);
  await expect(page.getByText('Piquages sans position connue dans les symboles choisis', { exact: false })).toContainText('supplier_nozzle');
  await apply(page);
  await save(page);
  await page.getByRole('button', { name: 'Construire', exact: true }).click();
  await page.locator('.react-flow__edge[data-id="primary"]').press('Enter');
  await expect(page.getByLabel('Piquage cible')).toHaveValue('supplier_nozzle');
  await expect(page.locator('.pid-port-warning')).toContainText('sans position connue');
  await page.getByLabel('Piquage cible').selectOption('AB');
  await expect(page.locator('.pid-port-warning')).toHaveCount(0);
  await save(page);
  expect((await (await request.get('/api/project')).json()).connections.find((item: { id: string }) => item.id === 'primary').target_port).toBe('AB');
});
