import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import type { LocalDraft } from '../src/draftStore';
import type { Project, Snapshot, WorkspaceSummary } from '../src/types';

async function snapshot(request: APIRequestContext): Promise<Snapshot> {
  const response = await request.get('/api/state');
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function mutate(request: APIRequestContext, path: string) {
  const project = await request.get('/api/project');
  const state = await snapshot(request);
  const { token } = await (await request.get('/api/session')).json();
  const response = await request.post(`/api${path}`, {
    headers: {
      'X-FAT-Token': token,
      'X-FAT-Project-ID': (await project.json()).id,
      'X-FAT-Project-Revision': project.headers()['x-fat-project-revision'],
      'X-FAT-Run-ID': state.run_id ?? '',
    },
    data: {},
  });
  expect(response.ok()).toBeTruthy();
}

async function boot(page: Page): Promise<Project> {
  const project: Project = await (await page.request.get('/api/project')).json();
  await page.goto('/');
  await expect(page.getByLabel('Nom du projet', { exact: true })).toHaveValue(project.name);
  return project;
}

async function drafts(page: Page): Promise<LocalDraft[]> {
  return page.evaluate(() => Object.keys(localStorage)
    .filter(key => key.startsWith('vanguard:draft:1:') && !key.startsWith('vanguard:draft:1:ack:'))
    .map(key => JSON.parse(localStorage.getItem(key)!)));
}

async function reloadWithDraft(page: Page) {
  page.once('dialog', dialog => dialog.accept());
  await page.reload();
  await expect(page.getByRole('region', { name: 'Brouillon retrouvé', exact: true })).toBeVisible();
}

test.beforeEach(async ({ page, request }) => {
  for (const path of ['health', 'project', 'state', 'catalog', 'schema']) {
    expect((await request.get(`/api/${path}`)).ok()).toBeTruthy();
  }
  if (['running', 'paused', 'error'].includes((await snapshot(request)).status)) await mutate(request, '/run/stop');
  await mutate(request, '/demo/load');
  await page.addInitScript(() => localStorage.setItem('vanguard:welcome-seen', '1'));
});

test('reprendre un rapport non enregistré puis changer de projet garde son brouillon sans le copier dans le nouveau rapport', async ({ page, request }) => {
  const original = await boot(page);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).sim_time_s).toBeGreaterThan(0);
  const runId = (await snapshot(request)).run_id!;
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('Arrêté');
  await page.getByRole('button', { name: 'Tendances & rapport', exact: true }).click();
  const observation = 'Observation saisie pour le test de récupération, sans conclusion FAT.';
  const marker = 'Note locale non ajoutée au journal.';
  await page.getByRole('textbox', { name: 'Observations', exact: true }).fill(observation);
  await page.getByLabel('Commentaire de l’essai', { exact: true }).fill(marker);
  await expect(page.getByText('Brouillon récupérable sur ce navigateur', { exact: true })).toBeVisible();
  expect((await snapshot(request)).result).toMatchObject({ verdict: 'not_evaluated', comment: '' });

  await reloadWithDraft(page);
  await page.getByRole('button', { name: 'Tendances & rapport', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Observations', exact: true })).toHaveValue('');
  await expect(page.getByLabel('Commentaire de l’essai', { exact: true })).toHaveValue('');
  await page.getByRole('button', { name: 'Reprendre le brouillon', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Observations', exact: true })).toHaveValue(observation);
  await expect(page.getByLabel('Commentaire de l’essai', { exact: true })).toHaveValue(marker);
  await expect(page.getByRole('combobox', { name: 'Résultat', exact: true })).toHaveValue('not_evaluated');
  expect((await snapshot(request)).result.comment).toBe('');

  await page.getByRole('button', { name: 'Nouveau', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Nom du projet', { exact: true }).fill('Projet sans observations héritées');
  const confirmation = page.waitForEvent('dialog');
  const creating = page.getByRole('button', { name: 'Créer le projet', exact: true }).click();
  const dialog = await confirmation;
  expect(dialog.type()).toBe('confirm');
  expect(dialog.message()).toContain('modifications non enregistrées');
  await dialog.accept();
  await creating;
  await expect(page.getByLabel('Nom du projet', { exact: true })).toHaveValue('Projet sans observations héritées');
  const next: Project = await (await request.get('/api/project')).json();
  expect(next.id).not.toBe(original.id);
  await page.getByRole('button', { name: 'Tendances & rapport', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Observations', exact: true })).toHaveValue('');
  await expect(page.getByLabel('Commentaire de l’essai', { exact: true })).toHaveValue('');
  await expect(page.getByRole('combobox', { name: 'Résultat', exact: true })).toHaveValue('not_evaluated');
  await expect(page.getByRole('button', { name: 'Enregistrer la conclusion', exact: true })).toBeDisabled();
  const stored = await drafts(page);
  expect(stored).toEqual(expect.arrayContaining([expect.objectContaining({
    project: expect.objectContaining({ id: original.id }),
    report: expect.objectContaining({ runId, comment: observation, marker, verdict: 'not_evaluated' }),
  })]));
  expect(stored.filter(draft => draft.project.id === next.id)).toEqual([]);
  const proof = await (await request.get(`/api/runs/${runId}/json`)).json();
  expect(proof.result).toMatchObject({ verdict: 'not_evaluated', comment: '' });
  expect(proof.events.some((event: { message: string }) => event.message === marker)).toBe(false);
});

test('le JSON de scénario retrouvé attend une reprise, une application et un enregistrement explicites', async ({ page, request }) => {
  const original = await boot(page);
  const scenario = original.scenarios.find(item => item.execution_mode !== 'guided')!;
  expect(scenario).toBeTruthy();
  await page.getByRole('button', { name: 'Scénarios', exact: true }).click();
  await page.locator('.scenario-list-item').filter({ hasText: scenario.name }).click();
  const steps = [{ at_s: 0, action: 'marker', message: 'Étape préparée pour le test de récupération.' }];
  const raw = JSON.stringify(steps, null, 2);
  await page.getByLabel('Étapes JSON du scénario', { exact: true }).fill(raw);
  await expect(page.getByText('Brouillon récupérable sur ce navigateur', { exact: true })).toBeVisible();
  expect((await (await request.get('/api/project')).json()).scenarios).toEqual(original.scenarios);

  await reloadWithDraft(page);
  await expect(page.getByLabel('Nom du projet', { exact: true })).toBeDisabled();
  expect((await (await request.get('/api/project')).json()).scenarios).toEqual(original.scenarios);
  await page.getByRole('button', { name: 'Reprendre le brouillon', exact: true }).click();
  await expect(page.getByLabel('Nom du scénario', { exact: true })).toHaveValue(scenario.name);
  await expect(page.getByLabel('Étapes JSON du scénario', { exact: true })).toHaveValue(raw);
  await expect(page.getByRole('button', { name: 'Enregistrer', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Démarrer', exact: true })).toBeDisabled();
  expect((await (await request.get('/api/project')).json()).scenarios).toEqual(original.scenarios);

  await page.getByRole('button', { name: 'Appliquer les étapes', exact: true }).click();
  await expect(page.getByText('Étapes appliquées au projet.', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Enregistrer', exact: true })).toBeEnabled();
  expect((await (await request.get('/api/project')).json()).scenarios).toEqual(original.scenarios);
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  const saved: Project = await (await request.get('/api/project')).json();
  expect(saved.scenarios.find(item => item.id === scenario.id)?.steps).toEqual([expect.objectContaining(steps[0])]);
  expect((await snapshot(request)).run_id).toBeNull();
  expect((await snapshot(request)).result.verdict).toBe('not_evaluated');
});

test('une archive du même projet garde les brouillons séparés par dossier et retrouve celui du dossier rouvert', async ({ page, request }) => {
  const original = await boot(page);
  const originalWorkspace: WorkspaceSummary = await (await request.get('/api/workspace')).json();
  await page.getByRole('button', { name: 'Ouvrir', exact: true }).click();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Exporter l’archive FAT', exact: true }).click();
  const archive = await downloaded;
  const bytes = await readFile((await archive.path())!);
  await page.getByRole('button', { name: 'Fermer la fenêtre', exact: true }).click();
  await page.getByLabel('Nom du projet', { exact: true }).fill('Brouillon du dossier original');
  await expect(page.getByText('Brouillon récupérable sur ce navigateur', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Ouvrir', exact: true }).click();
  page.once('dialog', dialog => dialog.accept());
  await page.getByLabel('Archive FAT à restaurer', { exact: true }).setInputFiles({ name: archive.suggestedFilename(), mimeType: 'application/zip', buffer: bytes });
  await expect(page.getByRole('status')).toContainText('nouveau dossier');
  const restoredWorkspace: WorkspaceSummary = await (await request.get('/api/workspace')).json();
  expect(restoredWorkspace.path).not.toBe(originalWorkspace.path);
  expect((await (await request.get('/api/project')).json()).id).toBe(original.id);
  await expect(page.getByRole('region', { name: 'Brouillon retrouvé', exact: true })).toHaveCount(0);
  await expect(page.getByLabel('Nom du projet', { exact: true })).toHaveValue(original.name);
  await expect(page.getByLabel('Nom du projet', { exact: true })).toBeEnabled();

  await page.getByLabel('Nom du projet', { exact: true }).fill('Brouillon du dossier restauré');
  await expect(page.getByText('Brouillon récupérable sur ce navigateur', { exact: true })).toBeVisible();
  const stored = await drafts(page);
  expect(stored).toEqual(expect.arrayContaining([
    expect.objectContaining({ scope: originalWorkspace.path, project: expect.objectContaining({ id: original.id, name: 'Brouillon du dossier original' }) }),
    expect.objectContaining({ scope: restoredWorkspace.path, project: expect.objectContaining({ id: original.id, name: 'Brouillon du dossier restauré' }) }),
  ]));
  await page.getByRole('button', { name: 'Ouvrir', exact: true }).click();
  page.once('dialog', dialog => dialog.accept());
  await page.locator(`.workspace-item[data-workspace="${originalWorkspace.id}"]`).getByRole('button').click();
  await expect(page.getByRole('region', { name: 'Brouillon retrouvé', exact: true })).toBeVisible();
  const recoveredDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Télécharger le brouillon', exact: true }).click();
  const recovered = JSON.parse(await readFile((await (await recoveredDownload).path())!, 'utf8'));
  expect(recovered).toMatchObject({ scope: originalWorkspace.path, project: { id: original.id, name: 'Brouillon du dossier original' } });
  await page.getByRole('button', { name: 'Reprendre le brouillon', exact: true }).click();
  await expect(page.getByLabel('Nom du projet', { exact: true })).toHaveValue('Brouillon du dossier original');
  expect((await (await request.get('/api/project')).json()).name).toBe(original.name);
  expect((await (await request.get('/api/workspace')).json()).path).toBe(originalWorkspace.path);
  expect((await drafts(page)).some(draft => draft.scope === restoredWorkspace.path && draft.project.name === 'Brouillon du dossier restauré')).toBe(true);
  expect((await snapshot(request)).run_id).toBeNull();
});
