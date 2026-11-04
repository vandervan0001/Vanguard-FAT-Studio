import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import type { Project, Snapshot } from '../src/types';

async function mutation(request: APIRequestContext, path: string, body: unknown = {}) {
  const session = await request.get('/api/session');
  const { token } = await session.json();
  return request.post(`/api${path}`, { headers: { 'X-FAT-Token': token }, data: body });
}

async function snapshot(request: APIRequestContext): Promise<Snapshot> {
  const response = await request.get('/api/state');
  expect(response.ok()).toBeTruthy();
  return response.json();
}

test.beforeEach(async ({ request, page }) => {
  const state = await snapshot(request);
  if (['running', 'paused', 'error'].includes(state.status)) expect((await mutation(request, '/run/stop')).ok()).toBeTruthy();
  expect((await mutation(request, '/demo/load')).ok()).toBeTruthy();
  page.on('dialog', dialog => dialog.accept());
});

async function boot(page: Page) {
  await page.goto('/');
  await expect(page.getByLabel('Nom du projet')).toHaveValue('TK-101 · Banc de remplissage');
  await expect(page.locator('.react-flow__node')).toHaveCount(7);
}

test('charger le laboratoire public, commander une pompe et injecter son défaut', async ({ page, request }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await boot(page);
  await page.getByRole('button', { name: 'Ouvrir', exact: true }).click();
  await page.getByRole('button', { name: 'Charger le laboratoire', exact: true }).click();
  const project: Project = await (await request.get('/api/project')).json();
  await expect(page.getByLabel('Nom du projet')).toHaveValue(project.name);
  await expect(page.locator('.react-flow__node')).toHaveCount(project.equipment.filter(item => !['digital_input', 'indicator'].includes(item.type)).length);
  expect(project.equipment.filter(item => item.type === 'tank')).toHaveLength(3);
  expect(project.equipment.filter(item => ['pump', 'pump_vfd'].includes(item.type))).toHaveLength(4);
  expect(project.tags.every(tag => !tag.node_id && !tag.plc_address)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('public-laboratory.png') });
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  await expect.poll(async () => (await snapshot(request)).sim_time_s).toBeGreaterThan(.3);
  await page.locator('.digital-control[data-tag="p101_request"] .digital-push').dblclick();
  await expect.poll(async () => (await snapshot(request)).tags.p101_command.value).toBe(true);
  await page.locator('.react-flow__node[data-id="P101"]').click();
  await page.getByRole('button', { name: 'Injecter', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).tags.p101_fault.value).toBe(true);
  await expect.poll(async () => (await snapshot(request)).tags.p101_running.value).toBe(false);
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
  expect(errors).toEqual([]);
});

test('recharger un scénario automatique en pause conserve sa sélection et son plan', async ({ page, request }) => {
  expect((await mutation(request, '/pilot/load')).ok()).toBeTruthy();
  await page.goto('/');
  const project: Project = await (await request.get('/api/project')).json();
  const scenario = project.scenarios.find(item => item.id === 'demo-stop')!;
  await expect(page.getByLabel('Nom du projet')).toHaveValue(project.name);
  await page.getByLabel('Scénario', { exact: true }).selectOption(scenario.id);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).sim_time_s).toBeGreaterThanOrEqual(1);
  await page.getByRole('button', { name: 'Mettre en pause', exact: true }).click();
  const paused = await snapshot(request);
  await page.reload();
  await expect(page.getByLabel('Scénario', { exact: true })).toHaveValue(scenario.id);
  await expect(page.locator('.palette')).toBeVisible();
  await expect(page.getByLabel('Scénario', { exact: true })).toBeEnabled();
  await expect(page.locator('.fat-run h3')).toHaveText(scenario.name);
  await expect(page.locator('.fat-timeline .step-result.passed').first()).toContainText('Conforme');
  await expect(page.locator('.fat-timeline .step-result.passed').first()).toContainText('Lu : TRUE');
  await page.getByRole('button', { name: 'Scénarios', exact: true }).click();
  await expect(page.getByLabel('Nom du scénario')).toHaveValue(scenario.name);
  await expect(page.getByLabel('Nom du scénario')).toBeEnabled();
  await page.getByRole('button', { name: 'P&ID', exact: true }).click();
  await expect(page.getByLabel('Scénario', { exact: true })).toHaveValue(scenario.id);
  const reloaded = await snapshot(request);
  expect(reloaded.run_id).toBe(paused.run_id);
  expect(reloaded.scenario.id).toBe(scenario.id);
  expect(reloaded.sim_time_s).toBe(paused.sim_time_s);
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
  await expect(page.getByLabel('Scénario', { exact: true })).toHaveValue(scenario.id);
});

test('éditer un vrai P&ID, sauvegarder puis recharger conserve les propriétés', async ({ page, request }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await boot(page);
  await page.screenshot({ path: testInfo.outputPath('pid-reviewed.png') });
  await page.getByRole('button', { name: 'Construire', exact: true }).click();
  await page.locator('.react-flow__node[data-id="P101"]').click();
  await page.getByLabel('Nom / repère').fill('P-101 test');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  await page.reload();
  await expect(page.locator('.react-flow__node[data-id="P101"]')).toContainText('P-101 test');
  const stored: Project = await (await request.get('/api/project')).json();
  expect(stored.equipment.find(item => item.id === 'P101')?.name).toBe('P-101 test');
  expect(errors).toEqual([]);
});

test('essai réel : boucle fermée, défaut, forçage, pause/reprise et exports', async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await boot(page);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  await expect(page.getByRole('button', { name: 'Enregistrer', exact: true })).toBeDisabled();
  await expect.poll(async () => (await snapshot(request)).sim_time_s).toBeGreaterThan(.5);
  await expect.poll(async () => Number((await snapshot(request)).tags.level.value)).toBeGreaterThan(25);

  await page.locator('.react-flow__node[data-id="P101"]').click();
  await page.getByRole('button', { name: 'Injecter', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).tags.pump_fault.value).toBe(true);
  await expect(page.locator('.react-flow__node[data-id="P101"]')).toContainText('DÉFAUT');
  await page.getByRole('button', { name: 'Lever', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).tags.pump_fault.value).toBe(false);

  await page.locator('.react-flow__node[data-id="LT101"]').click();
  await page.getByLabel('Forçage LevelPct').fill('42');
  await page.locator('.analog-control[data-tag="level"]').getByRole('button', { name: 'Forcer', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).tags.level.forced).toBe(true);
  await expect.poll(async () => (await snapshot(request)).tags.level.value).toBe(42);
  await page.getByRole('button', { name: 'Libérer LevelPct', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).tags.level.forced).toBe(false);

  await page.getByRole('button', { name: 'Mettre en pause', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En pause');
  const paused = (await snapshot(request)).sim_time_s;
  await page.waitForTimeout(250); // verifies the real loop stops advancing across two model periods
  expect((await snapshot(request)).sim_time_s).toBe(paused);
  await page.getByRole('button', { name: 'Reprendre', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).sim_time_s).toBeGreaterThan(paused);
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('Arrêté');

  await page.getByRole('button', { name: 'Tendances & rapport', exact: true }).click();
  await page.getByLabel('Commentaire de l’essai').fill('Mesures et défaut moteur contrôlés.');
  await page.getByRole('button', { name: 'Ajouter', exact: true }).click();
  await page.getByRole('combobox', { name: 'Résultat', exact: true }).selectOption('pass');
  await page.getByLabel('Observations', { exact: true }).fill('Essai automatique du parcours navigateur.');
  await page.getByRole('button', { name: 'Enregistrer la conclusion', exact: true }).click();
  await expect(page.getByText('Conclusion enregistrée', { exact: true })).toBeVisible();
  const csvPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Données CSV', exact: true }).click();
  const csvFile = await csvPromise;
  const csv = await readFile((await csvFile.path())!, 'utf8');
  expect(csv).toContain('LevelPct');
  expect(csv.split('\n').length).toBeGreaterThan(20);
  const reportPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Rapport FAT', exact: true }).click();
  const report = await readFile((await (await reportPromise).path())!, 'utf8');
  expect(report).toContain('Essai automatique du parcours navigateur.');
  expect(report).toContain('Mesures et défaut moteur contrôlés.');
  expect(errors).toEqual([]);
});

test('un JSON de scénario invalide reste un brouillon et ne casse pas React', async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await boot(page);
  await page.getByRole('button', { name: 'Scénarios', exact: true }).click();
  await page.getByRole('button', { name: /01 · Cycle de référence/ }).click();
  const editor = page.getByLabel('Étapes JSON du scénario');
  await editor.fill('[{"at_s":0,"action":"marker","message":{"unsafe":"object"}}]');
  await page.getByRole('button', { name: 'Appliquer les étapes', exact: true }).click();
  await expect(page.locator('.inline-error')).toContainText('message doit être du texte');
  await expect(page.getByRole('button', { name: 'Démarrer', exact: true })).toBeDisabled();
  await editor.fill('[{"at_s":0,"action":"marker","message":"Scénario contrôlé"}]');
  await page.getByRole('button', { name: 'Appliquer les étapes', exact: true }).click();
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  const stored: Project = await (await request.get('/api/project')).json();
  expect(stored.scenarios.find(scenario => scenario.id === 'reference')?.steps[0].message).toBe('Scénario contrôlé');
  expect(errors).toEqual([]);
});

test('un import invalide préserve le projet affiché et enregistré', async ({ page, request }) => {
  await boot(page);
  await page.locator('.projectbar input[type="file"][accept=".json,application/json"]').setInputFiles({ name: 'invalide.json', mimeType: 'application/json', buffer: Buffer.from('{"id":"bad","name":"Ne pas charger","equipment":"oops"}') });
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByLabel('Nom du projet')).toHaveValue('TK-101 · Banc de remplissage');
  await expect(page.locator('.react-flow__node')).toHaveCount(7);
  expect((await (await request.get('/api/project')).json()).id).toBe('tank-demo');
});

test('un autre onglet change de projet : commandes bloquées et brouillon récupérable', async ({ page, request }) => {
  await boot(page);
  await page.getByLabel('Nom du projet').fill('Brouillon à conserver');
  const create = await mutation(request, '/projects', { name: 'Autre onglet' });
  expect(create.ok()).toBeTruthy();
  await expect(page.getByRole('alert')).toContainText('Le projet actif a changé');
  await expect(page.getByRole('button', { name: 'Démarrer', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Enregistrer', exact: true })).toBeDisabled();
  const filePromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Télécharger mon brouillon', exact: true }).click();
  const data = JSON.parse(await readFile((await (await filePromise).path())!, 'utf8'));
  expect(data.project.name).toBe('Brouillon à conserver');
  expect((await (await request.get('/api/project')).json()).name).toBe('Autre onglet');
});

test('une nouvelle révision du même projet ne remplace pas silencieusement le brouillon', async ({ page, request }) => {
  await boot(page);
  await page.getByLabel('Nom du projet').fill('Mon brouillon non enregistré');
  const response = await request.get('/api/project');
  const project: Project = await response.json();
  const previousRevision = response.headers()['x-fat-project-revision'];
  expect(previousRevision).toBeTruthy();
  const { token } = await (await request.get('/api/session')).json();
  project.name = 'Révision enregistrée dans un autre onglet';
  const updated = await request.put('/api/project', { headers: { 'X-FAT-Token': token, 'X-FAT-Project-ID': project.id, 'X-FAT-Project-Revision': previousRevision }, data: project });
  expect(updated.ok()).toBeTruthy();
  await expect(page.getByRole('alert')).toContainText('Le projet actif a changé');
  await expect(page.getByRole('button', { name: 'Enregistrer', exact: true })).toBeDisabled();
  await expect(page.getByLabel('Nom du projet')).toHaveValue('Mon brouillon non enregistré');
  // A stale API write must also fail, including the interval before the next UI poll.
  const rejected = await request.put('/api/project', { headers: { 'X-FAT-Token': token, 'X-FAT-Project-ID': project.id, 'X-FAT-Project-Revision': previousRevision }, data: { ...project, name: 'Écriture périmée à refuser' } });
  expect(rejected.status()).toBe(409);
  expect((await (await request.get('/api/project')).json()).name).toBe('Révision enregistrée dans un autre onglet');
});
