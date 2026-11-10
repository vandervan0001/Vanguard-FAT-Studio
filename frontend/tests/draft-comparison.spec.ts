import { expect, test, type Page } from '@playwright/test';
import { compareDraft, draftErrorKey, mergeDraft } from '../src/draftMerge';
import type { Project } from '../src/types';

async function projectResponse(page: Page) {
  const response = await page.request.get('/api/project');
  return { project: await response.json() as Project, revision: response.headers()['x-fat-project-revision'] };
}
async function saveElsewhere(page: Page, update: (project: Project) => void) {
  const { project, revision } = await projectResponse(page);
  const { token } = await (await page.request.get('/api/session')).json();
  const state = await (await page.request.get('/api/state')).json();
  update(project);
  const response = await page.request.put('/api/project', { headers: { 'X-FAT-Token': token, 'X-FAT-Project-ID': project.id, 'X-FAT-Project-Revision': revision, 'X-FAT-Run-ID': state.run_id ?? '' }, data: project });
  expect(response.ok()).toBe(true);
}
async function freshProject(page: Page) {
  for (const path of ['health', 'project', 'state', 'catalog', 'schema']) expect((await page.request.get(`/api/${path}`)).ok()).toBeTruthy();
  await page.goto('/');
  await page.getByLabel('Nom du projet', { exact: true }).waitFor();
  const stop = page.getByRole('button', { name: 'Arrêter l’essai', exact: true });
  if (await stop.isEnabled()) await stop.click();
  await page.getByRole('button', { name: 'Nouveau', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Nom du projet', { exact: true }).fill('Base de comparaison');
  await page.getByRole('button', { name: 'Créer le projet', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByLabel('Nom du projet', { exact: true })).toHaveValue('Base de comparaison');
}
async function staleDraft(page: Page, conflict = false) {
  await freshProject(page);
  await page.getByLabel('Nom du projet', { exact: true }).fill('Nom dans mon brouillon');
  await expect(page.getByText('Brouillon récupérable sur ce navigateur', { exact: true })).toBeVisible();
  await saveElsewhere(page, project => { project.description = 'Description écrite dans un autre onglet'; if (conflict) project.name = 'Nom enregistré ailleurs'; });
  page.once('dialog', dialog => dialog.accept());
  await page.reload();
  await page.getByRole('button', { name: 'Comparer les versions', exact: true }).click();
  const modal = page.getByRole('dialog', { name: 'Comparer le brouillon', exact: true });
  await expect(modal.getByText('Vérification des versions…', { exact: true })).toHaveCount(0);
  await expect(modal.getByRole('checkbox')).toHaveCount(1);
  return modal;
}

test('reprendre un champ sans conflit garde les autres modifications et attend Enregistrer', async ({ page }, testInfo) => {
  const modal = await staleDraft(page);
  await expect(modal.getByRole('checkbox')).toBeChecked();
  await page.screenshot({ path: testInfo.outputPath('comparaison-brouillon.png') });
  await modal.getByRole('button', { name: 'Reprendre les champs choisis' }).click();
  await expect(modal).toHaveCount(0);
  await expect(page.getByLabel('Nom du projet', { exact: true })).toHaveValue('Nom dans mon brouillon');
  expect((await projectResponse(page)).project.name).toBe('Base de comparaison');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  expect((await projectResponse(page)).project).toMatchObject({ name: 'Nom dans mon brouillon', description: 'Description écrite dans un autre onglet' });
});

test('un conflit reste décoché et une nouvelle révision empêche l’application', async ({ page }) => {
  const modal = await staleDraft(page, true);
  await expect(modal.getByRole('checkbox')).not.toBeChecked();
  await expect(modal.getByText('Conflit à choisir', { exact: true })).toBeVisible();
  await expect(modal.getByRole('button', { name: 'Reprendre les champs choisis' })).toBeDisabled();
  await modal.getByRole('checkbox').check();
  let release!: () => void, requested!: () => void;
  const waiting = new Promise<void>(resolve => { requested = resolve; });
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/validate/preview', async route => { requested(); await held; await route.continue(); });
  await modal.getByRole('button', { name: 'Reprendre les champs choisis' }).click();
  await waiting;
  await saveElsewhere(page, project => { project.name = 'Troisième version'; });
  release();
  await expect(modal.getByRole('alert').first()).toBeVisible();
  expect((await projectResponse(page)).project.name).toBe('Troisième version');
  const stored = await page.evaluate(() => Object.keys(localStorage).filter(key => key.startsWith('vanguard:draft:1:') && !key.includes(':ack:')).map(key => JSON.parse(localStorage.getItem(key)!)));
  expect(stored.some(draft => draft.project.name === 'Nom dans mon brouillon')).toBe(true);
});

test('un choix explicite résout le conflit et annuler ne modifie aucune version', async ({ page }) => {
  let modal = await staleDraft(page, true);
  await modal.getByRole('checkbox').check();
  await modal.getByRole('button', { name: 'Annuler', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Brouillon retrouvé' })).toBeVisible();
  expect((await projectResponse(page)).project.name).toBe('Nom enregistré ailleurs');
  await page.getByRole('button', { name: 'Comparer les versions' }).click();
  modal = page.getByRole('dialog', { name: 'Comparer le brouillon' });
  await expect(modal.getByRole('checkbox')).not.toBeChecked();
  await modal.getByRole('checkbox').check();
  await modal.getByRole('button', { name: 'Reprendre les champs choisis' }).click();
  await expect(modal).toHaveCount(0);
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  expect((await projectResponse(page)).project.name).toBe('Nom dans mon brouillon');
});

test('la comparaison conserve suppressions, ajouts et ordre de la version enregistrée', async ({ page }) => {
  await freshProject(page);
  const base = (await projectResponse(page)).project;
  const tag = { id: 'sensor', name: 'Capteur', direction: 'input' as const, data_type: 'REAL' as const, unit: '%', initial_value: 0, min: 0, max: 100, node_id: '', writable: false };
  base.tags = [tag];
  const local = structuredClone(base), current = structuredClone(base);
  local.tags[0].name = 'Nom local';
  current.tags = [];
  const changes = compareDraft(base, local, current);
  expect(changes).toHaveLength(1);
  expect(changes[0].conflict).toBe(true);
  expect(mergeDraft(current, changes, new Set()).tags).toEqual([]);
  expect(mergeDraft(current, changes, new Set([changes[0].key])).tags[0].name).toBe('Nom local');
  current.tags = [{ ...tag, id: 'elsewhere', name: 'Ajout distant' }, tag];
  local.tags.push({ ...tag, id: 'local', name: 'Ajout local' });
  local.tags[0].unit = 'bar';
  const nextChanges = compareDraft(base, local, current);
  const merged = mergeDraft(current, nextChanges, new Set(nextChanges.map(change => change.key)));
  expect(merged.tags.map(item => item.id)).toEqual(['elsewhere', 'sensor', 'local']);
  expect(merged.tags[1]).toMatchObject({ name: 'Nom local', unit: 'bar' });
  expect(current.tags[1]).toEqual(tag);
  const error = { path: 'tags.0.writable', message: 'Écriture requise' };
  expect(draftErrorKey(base, error)).not.toBe(draftErrorKey(current, error));
  expect(draftErrorKey(base, error)).toBe(draftErrorKey(current, { ...error, path: 'tags.1.writable' }));
});

test('fermer une comparaison pendant sa vérification conserve le brouillon et ignore la réponse tardive', async ({ page }) => {
  const modal = await staleDraft(page);
  let release!: () => void, requested!: () => void;
  const waiting = new Promise<void>(resolve => { requested = resolve; });
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/validate/preview', async route => { const response = await route.fetch(); requested(); await held; await route.fulfill({ response }).catch(() => undefined); });
  await modal.getByRole('button', { name: 'Reprendre les champs choisis' }).click();
  await waiting;
  await page.keyboard.press('Escape');
  await expect(modal).toHaveCount(0);
  release();
  await expect(page.getByRole('region', { name: 'Brouillon retrouvé' })).toBeVisible();
  await expect(page.getByLabel('Nom du projet', { exact: true })).toHaveValue('Base de comparaison');
  expect((await projectResponse(page)).project.name).toBe('Base de comparaison');
});

test('comparer un projet ne reporte pas ses observations dans un autre essai', async ({ page }) => {
  await freshProject(page);
  await page.getByRole('button', { name: 'Insérer un circuit de remplissage', exact: true }).click();
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect.poll(async () => (await (await page.request.get('/api/state')).json()).sim_time_s).toBeGreaterThan(0);
  const run = (await (await page.request.get('/api/state')).json()).run_id;
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
  await page.getByRole('button', { name: 'Tendances & rapport', exact: true }).click();
  await page.getByRole('textbox', { name: 'Observations', exact: true }).fill('Observation locale pour ce test de récupération.');
  await page.getByLabel('Nom du projet', { exact: true }).fill('Projet avec notes séparées');
  await expect(page.getByText('Brouillon récupérable sur ce navigateur', { exact: true })).toBeVisible();
  await saveElsewhere(page, project => { project.description = 'Révision enregistrée après cet essai'; });
  page.once('dialog', dialog => dialog.accept()); await page.reload();
  await page.getByRole('button', { name: 'Comparer les versions' }).click();
  const modal = page.getByRole('dialog', { name: 'Comparer le brouillon' });
  await expect(modal.getByRole('checkbox')).toHaveCount(1);
  const download = page.waitForEvent('download');
  await modal.getByRole('button', { name: 'Reprendre les champs choisis' }).click();
  expect((await download).suggestedFilename()).toContain('brouillon-complet');
  await expect(modal).toHaveCount(0);
  await page.getByRole('button', { name: 'Tendances & rapport', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Observations', exact: true })).toHaveValue('');
  const oldRun = await (await page.request.get(`/api/runs/${run}/json`)).json();
  expect(oldRun.result).toMatchObject({ verdict: 'not_evaluated', comment: '' });
  const records = await page.evaluate(() => Object.keys(localStorage).filter(key => key.startsWith('vanguard:draft:1:') && !key.includes(':ack:')).map(key => JSON.parse(localStorage.getItem(key)!)));
  expect(records.some(draft => draft.report.runId === run && draft.report.comment === 'Observation locale pour ce test de récupération.')).toBe(true);
});
