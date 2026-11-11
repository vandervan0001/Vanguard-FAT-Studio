import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';
import type { Project, Snapshot } from '../src/types';

async function headers(request: APIRequestContext) {
  const [session, project, state] = await Promise.all([request.get('/api/session'), request.get('/api/project'), request.get('/api/state')]);
  return { 'X-FAT-Token': (await session.json()).token, 'X-FAT-Project-ID': (await project.json()).id, 'X-FAT-Project-Revision': project.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': (await state.json()).run_id ?? '' };
}
async function snapshot(request: APIRequestContext): Promise<Snapshot> { return (await request.get('/api/state')).json(); }
async function openDrawing(page: Page) {
  await page.getByRole('button', { name: 'Échanges P&ID', exact: true }).click();
  await page.getByRole('button', { name: 'Mise en page', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Mise en page du P&ID' })).toBeVisible();
}

test.beforeEach(async ({ page, request }) => {
  expect((await request.get('/api/health')).ok()).toBe(true);
  if (['running', 'paused', 'error'].includes((await snapshot(request)).status)) expect((await request.post('/api/run/stop', { headers: await headers(request), data: {} })).ok()).toBe(true);
  expect((await request.post('/api/demo/load', { headers: await headers(request), data: {} })).ok()).toBe(true);
  await page.goto('/');
  await expect(page.getByLabel('Nom du projet')).toHaveValue('TK-101 · Banc de remplissage');
});

test('mise en page, aperçu réel et sauvegarde gardent tout le brouillon du projet', async ({ page, request }, testInfo) => {
  test.setTimeout(60_000);
  const original: Project = await (await request.get('/api/project')).json();
  await page.getByLabel('Nom du projet').fill('Schéma local à conserver');
  await openDrawing(page);
  await expect(page.getByLabel('Titre du dessin', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('Date d’émission', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('Entreprise', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('Statut déclaré', { exact: true })).toHaveValue('draft');
  await page.getByLabel('Titre du dessin', { exact: true }).fill('Transfert de liquide · feuille de test');
  await page.getByLabel('Numéro du document', { exact: true }).fill('PID-LOCAL-101');
  await page.getByLabel('Indice de révision', { exact: true }).fill('02');
  await page.getByLabel('Date d’émission', { exact: true }).fill('2026-11-11');
  await page.getByText('Entreprise et projet', { exact: true }).click();
  await page.getByLabel('Entreprise', { exact: true }).fill('Entreprise de test locale');
  await page.getByLabel('Référence du projet', { exact: true }).fill('LOCAL-101');
  await page.getByText('Format et folio', { exact: true }).click();
  await page.getByLabel('Format du papier', { exact: true }).selectOption('A4');
  await page.getByLabel('Orientation', { exact: true }).selectOption('portrait');
  await page.getByLabel('Numéro du folio', { exact: true }).fill('2');
  await expect(page.getByRole('button', { name: 'Générer l’aperçu', exact: true })).toBeDisabled();
  await page.getByLabel('Nombre total de folios', { exact: true }).fill('2');
  await page.getByText('Historique des révisions (0 / 5)', { exact: true }).click();
  for (let index = 0; index < 5; index++) await page.getByRole('button', { name: 'Ajouter une révision', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Ajouter une révision', exact: true })).toBeDisabled();
  for (const index of [5, 4, 3, 2]) await page.getByRole('button', { name: `Retirer la révision ${index}`, exact: true }).click();
  await page.getByLabel('Indice historique 1', { exact: true }).fill('02');
  await page.getByLabel('Description historique 1', { exact: true }).fill('Émission locale pour revue');
  const before = await request.get('/api/project');
  const beforeState = await snapshot(request);
  const previewRequest = page.waitForRequest(event => new URL(event.url()).pathname === '/api/pid/preview');
  const previewResponse = page.waitForResponse(event => new URL(event.url()).pathname === '/api/pid/preview');
  await page.getByRole('button', { name: 'Générer l’aperçu', exact: true }).click();
  expect((await previewRequest).postDataJSON().paper_size).toBe('A4');
  await expect(page.getByRole('img', { name: 'Aperçu de la feuille P&ID avec son cartouche' })).toBeVisible({ timeout: 30_000 });
  const renderedPreview = await (await previewResponse).json();
  await writeFile(testInfo.outputPath('preview-sheet.png'), Buffer.from(renderedPreview.image_data_url.split(',', 2)[1], 'base64'));
  await expect(page.locator('.pid-preview-size')).toContainText('210 × 297 mm');
  const afterPreview = await request.get('/api/project');
  expect(await afterPreview.json()).toEqual(await before.json());
  expect(afterPreview.headers()['x-fat-project-revision']).toBe(before.headers()['x-fat-project-revision']);
  expect((await snapshot(request)).write_count).toBe(beforeState.write_count);
  await page.getByRole('dialog').evaluate(element => { element.scrollTop = 0; });
  await page.screenshot({ path: testInfo.outputPath('drafting-preview-desktop.png') });
  await page.getByRole('button', { name: 'Appliquer au projet', exact: true }).click();
  expect((await (await request.get('/api/project')).json()).name).toBe(original.name);
  await page.getByRole('button', { name: 'Exporter le P&ID', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Télécharger PDF', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Mise en page', exact: true }).click();
  let releaseSave!: () => void, saveEntered!: () => void;
  const saveGate = new Promise<void>(resolve => { releaseSave = resolve; });
  const saving = new Promise<void>(resolve => { saveEntered = resolve; });
  await page.route('**/api/project', async route => { if (route.request().method() !== 'PUT') return route.continue(); saveEntered(); await saveGate; return route.continue(); });
  const savedResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/project' && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Enregistrer la mise en page', exact: true }).click();
  await saving;
  try {
    await page.getByRole('button', { name: 'Fermer les échanges P&ID', exact: true }).click();
    await expect(page.getByLabel('Nom du projet')).toBeDisabled();
  } finally { releaseSave(); }
  expect((await savedResponse).ok()).toBe(true);
  await expect(page.getByLabel('Nom du projet')).toBeEnabled();
  await page.unroute('**/api/project');
  await openDrawing(page);
  await expect(page.locator('.pid-progress')).toContainText('Mise en page et brouillon du projet enregistrés');
  await page.getByLabel('Indice de révision', { exact: true }).fill('03');
  await page.keyboard.press('Control+s');
  await expect.poll(async () => (await (await request.get('/api/project')).json()).pid_drawing.revision).toBe('03');
  await expect(page.getByRole('button', { name: 'Enregistrer la mise en page', exact: true })).toBeEnabled();
  const saved: Project = await (await request.get('/api/project')).json();
  expect(saved.name).toBe('Schéma local à conserver');
  expect(saved.equipment).toEqual(original.equipment);
  expect(saved.connections).toEqual(original.connections);
  expect(saved.pid_drawing).toMatchObject({ company: 'Entreprise de test locale', paper_size: 'A4', orientation: 'portrait', revision: '03', issue_date: '2026-11-11', sheet_number: 2, sheet_total: 2, approved_by: '', status: 'draft' });
  expect(saved.pid_drawing!.revisions).toHaveLength(1);
  await page.getByRole('button', { name: 'Exporter le P&ID', exact: true }).click();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Télécharger JSON', exact: true }).click();
  expect(JSON.parse(await readFile((await (await download).path())!, 'utf8')).drawing).toEqual(saved.pid_drawing);
  await page.reload();
  await openDrawing(page);
  await expect(page.getByLabel('Numéro du document', { exact: true })).toHaveValue('PID-LOCAL-101');
  await page.getByRole('button', { name: 'Générer l’aperçu', exact: true }).click();
  await expect(page.getByRole('img', { name: 'Aperçu de la feuille P&ID avec son cartouche' })).toBeVisible({ timeout: 30_000 });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('dialog').evaluate(element => { element.scrollTop = 0; });
  await page.screenshot({ path: testInfo.outputPath('drafting-fields-mobile.png') });
  expect(await page.locator('.pid-exchange').evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
});

test('une erreur 409 et un changement de contexte conservent la mise en page sans rejeu', async ({ page, request }) => {
  await openDrawing(page);
  await page.getByLabel('Numéro du document', { exact: true }).fill('BROUILLON-CONSERVE');
  await page.getByRole('button', { name: 'Fermer les échanges P&ID', exact: true }).click();
  await page.keyboard.press('Control+s');
  await expect(page.getByRole('alert')).toContainText('Une mise en page est en préparation');
  let downloads = 0;
  page.on('download', () => downloads++);
  await page.getByRole('button', { name: 'Exporter', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('avant de sauvegarder ou d’exporter le projet');
  expect(downloads).toBe(0);
  await page.getByRole('button', { name: 'Fermer le message d’erreur', exact: true }).click();
  await openDrawing(page);
  let previews = 0;
  await page.route('**/api/pid/preview', route => { previews++; return route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ detail: 'Contexte périmé de l’aperçu.' }) }); });
  await page.getByRole('button', { name: 'Générer l’aperçu', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Contexte périmé');
  expect(previews).toBe(1);
  await expect(page.getByLabel('Numéro du document', { exact: true })).toHaveValue('BROUILLON-CONSERVE');
  await page.unroute('**/api/pid/preview');
  const old: Project = await (await request.get('/api/project')).json();
  expect((await request.put('/api/project', { headers: await headers(request), data: { ...old, name: 'Modification distante' } })).ok()).toBe(true);
  await expect(page.getByRole('button', { name: 'Enregistrer la mise en page', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Fermer les échanges P&ID', exact: true }).click();
  await openDrawing(page);
  await expect(page.getByLabel('Numéro du document', { exact: true })).toHaveValue('BROUILLON-CONSERVE');
  expect((await (await request.get('/api/project')).json()).pid_drawing.document_number).toBe('');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Télécharger le brouillon de mise en page', exact: true }).click();
  expect(JSON.parse(await readFile((await (await download).path())!, 'utf8')).pid_drawing.document_number).toBe('BROUILLON-CONSERVE');
  expect(previews).toBe(1);
});

test('l’aperçu passif ne bloque ni forçage ni arrêt et sa réponse tardive ne modifie pas l’essai', async ({ page, request }) => {
  let release!: () => void, entered!: () => void;
  let released = false;
  const gate = new Promise<void>(resolve => { release = () => { released = true; resolve(); }; });
  const started = new Promise<void>(resolve => { entered = resolve; });
  // Transport/concurrency witness only; the first test uses the real renderer.
  await page.route('**/api/pid/preview', async route => { entered(); await gate; await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ image_data_url: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII=', width_mm: 420, height_mm: 297, warnings: [] }) }); });
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  await openDrawing(page);
  await page.getByLabel('Titre du dessin', { exact: true }).fill('Aperçu pendant un essai');
  await page.getByRole('button', { name: 'Générer l’aperçu', exact: true }).click();
  await started;
  let stopped: Snapshot | null = null;
  try {
    await page.getByRole('button', { name: 'Fermer les échanges P&ID', exact: true }).click();
    await page.locator('.analog-control[data-tag="level"]').getByLabel('Forçage LevelPct', { exact: true }).fill('42');
    const forced = page.waitForResponse(response => new URL(response.url()).pathname === '/api/force/stimulus');
    await page.locator('.analog-control[data-tag="level"]').getByRole('button', { name: 'Forcer', exact: true }).click();
    expect((await forced).ok()).toBe(true); expect(released).toBe(false);
    const stop = page.waitForResponse(response => new URL(response.url()).pathname === '/api/run/stop');
    await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
    expect((await stop).ok()).toBe(true); expect(released).toBe(false);
    stopped = await snapshot(request);
  } finally { release(); }
  await openDrawing(page);
  await expect(page.getByRole('img', { name: 'Aperçu de la feuille P&ID avec son cartouche' })).toBeVisible();
  const after = await snapshot(request);
  expect(after.status).toBe('stopped'); expect(after.run_id).toBe(stopped!.run_id); expect(after.write_count).toBe(stopped!.write_count);
  await expect(page.getByLabel('Titre du dessin', { exact: true })).toHaveValue('Aperçu pendant un essai');
});
