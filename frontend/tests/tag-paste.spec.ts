import { expect, test, type Page } from '@playwright/test';
import type { Project } from '../src/types';

async function fixture(page: Page): Promise<Project> {
  for (const path of ['health', 'project', 'state', 'catalog', 'schema']) expect((await page.request.get(`/api/${path}`)).ok()).toBeTruthy();
  const { token } = await (await page.request.get('/api/session')).json();
  const before = await page.request.get('/api/project');
  const state = await (await page.request.get('/api/state')).json();
  let headers = { 'X-FAT-Token': token, 'X-FAT-Project-ID': (await before.json()).id, 'X-FAT-Project-Revision': before.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': state.run_id ?? '' };
  if (['running', 'paused', 'error'].includes(state.status)) expect((await page.request.post('/api/run/stop', { headers })).ok()).toBeTruthy();
  const created = await page.request.post('/api/projects', { headers, data: { name: 'Collage · essai isolé' } });
  expect(created.ok(), await created.text()).toBeTruthy();
  const project: Project = await created.json();
  const current = await page.request.get('/api/project');
  const nextState = await (await page.request.get('/api/state')).json();
  headers = { ...headers, 'X-FAT-Project-ID': project.id, 'X-FAT-Project-Revision': current.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': nextState.run_id ?? '' };
  project.tags = [{ id: 'keep', name: 'Pression conservée', direction: 'input', data_type: 'REAL', unit: 'bar', initial_value: 1.5, min: 0, max: 10, writable: true, node_id: 'ns=2;s=Pressure', plc_address: '%IW264', plc_symbol: 'Pressure' }];
  project.scenarios = [{ id: 'watch', name: 'Observation conservée', description: '', duration_s: 2, steps: [], trend_tags: ['keep'] }];
  const persisted = await page.request.put('/api/project', { headers, data: project });
  expect(persisted.ok(), await persisted.text()).toBeTruthy();
  await page.goto('/');
  await page.getByLabel('Nom du projet', { exact: true }).waitFor();
  const resume = page.getByRole('button', { name: /Reprendre mon projet/ });
  if (await resume.isVisible()) await resume.click();
  await page.getByRole('button', { name: /^Variables & mapping/ }).click();
  return persisted.json();
}

async function openPaste(page: Page, text: string) {
  await page.getByRole('button', { name: 'Coller des tags Excel', exact: true }).click();
  const modal = page.getByRole('dialog', { name: 'Coller des tags Excel', exact: true });
  await modal.getByRole('textbox', { name: 'Tableau de tags', exact: true }).fill(text);
  await modal.getByRole('button', { name: 'Analyser le tableau', exact: true }).click();
  await expect(modal.getByRole('region', { name: 'Correspondance des colonnes' })).toBeVisible();
  return modal;
}

async function save(page: Page): Promise<Project> {
  const response = page.waitForResponse(response => response.url().endsWith('/api/project') && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  expect((await response).ok()).toBeTruthy();
  await expect(page.locator('.project-subtitle')).toContainText('Enregistré');
  return (await page.request.get('/api/project')).json();
}

test('un tableau Excel se relit par colonnes et persiste uniquement après application et enregistrement', async ({ page }, testInfo) => {
  const original = await fixture(page);
  const modal = await openPaste(page, 'Nom\tSens\tFormat\tAdresse Siemens\nP101_Running\tentrée\tBOOL\t%I1.0');
  await expect(modal.getByRole('button', { name: 'Préparer l’aperçu', exact: true })).toBeDisabled();
  await modal.getByRole('combobox', { name: 'Colonne 3 : Format', exact: true }).selectOption('data_type');
  await modal.getByRole('button', { name: 'Préparer l’aperçu', exact: true }).click();
  const result = modal.getByRole('region', { name: 'Aperçu des tags collés' });
  await expect(result).toContainText('1 ajout(s), 0 modification(s), 0 suppression(s)');
  await expect(result.getByRole('cell', { name: 'Désactivée', exact: true })).toBeVisible();
  expect(await (await page.request.get('/api/project')).json()).toEqual(original);
  await page.screenshot({ path: testInfo.outputPath('collage-excel-apercu.png') });
  await modal.getByRole('button', { name: 'Appliquer l’import au brouillon', exact: true }).click();
  await expect(modal).toHaveCount(0);
  expect(await (await page.request.get('/api/project')).json()).toEqual(original);
  const final = await save(page);
  expect(final.tags).toHaveLength(2);
  expect(final.tags[0]).toEqual(original.tags[0]);
  expect(final.tags[1]).toMatchObject({ name: 'P101_Running', data_type: 'BOOL', direction: 'input', writable: false, initial_value: false, plc_address: '%I1.0', node_id: '' });
  await page.reload();
  expect((await (await page.request.get('/api/project')).json()).tags).toEqual(final.tags);
  expect((await (await page.request.get('/api/state')).json()).write_count).toBe(0);
});

test('un CSV à point-virgule passe par la revue des colonnes et accepte les décimales françaises', async ({ page }) => {
  await fixture(page);
  await page.getByLabel('Importer une liste de variables', { exact: true }).setInputFiles({ name: 'mes-tags.csv', mimeType: 'text/csv', buffer: Buffer.from('Nom;Sens;Type;Valeur initiale;Unité\nDébit;input;REAL;12,5;l/s') });
  const modal = page.getByRole('dialog', { name: 'Coller des tags Excel', exact: true });
  await expect(modal.getByRole('textbox', { name: 'Tableau de tags' })).toHaveValue(/12,5/);
  await modal.getByRole('button', { name: 'Analyser le tableau', exact: true }).click();
  await expect(modal.getByRole('region', { name: 'Correspondance des colonnes' })).toContainText('Point-virgule');
  await modal.getByRole('button', { name: 'Préparer l’aperçu', exact: true }).click();
  await expect(modal.getByRole('region', { name: 'Aperçu des tags collés' })).toContainText('12.5');
  await modal.getByRole('button', { name: 'Appliquer l’import au brouillon', exact: true }).click();
  const final = await save(page);
  expect(final.tags.at(-1)).toMatchObject({ name: 'Débit', initial_value: 12.5, unit: 'l/s', writable: false });
});

test('les erreurs par ligne empêchent une application partielle et la correction reste dans la fenêtre', async ({ page }) => {
  const original = await fixture(page);
  const modal = await openPaste(page, 'Nom;Sens;Type;Écriture\nCorrect;input;BOOL;non\nInterdit;output;BOOL;oui\nInconnu;input;WORD;non');
  await modal.getByRole('button', { name: 'Préparer l’aperçu', exact: true }).click();
  const result = modal.getByRole('region', { name: 'Aperçu des tags collés' });
  await expect(result.getByRole('alert')).toContainText('Ligne 3');
  await expect(result.getByRole('alert')).toContainText('Ligne 4');
  await expect(modal.getByRole('button', { name: 'Appliquer l’import au brouillon', exact: true })).toBeDisabled();
  expect(await (await page.request.get('/api/project')).json()).toEqual(original);
  await modal.getByRole('textbox', { name: 'Tableau de tags' }).fill('Nom;Sens;Type;Écriture\nCorrect;input;BOOL;non');
  await expect(result).toHaveCount(0);
  await modal.getByRole('button', { name: 'Analyser le tableau', exact: true }).click();
  await modal.getByRole('button', { name: 'Préparer l’aperçu', exact: true }).click();
  await expect(modal.getByRole('button', { name: 'Appliquer l’import au brouillon', exact: true })).toBeEnabled();
  await modal.getByRole('button', { name: 'Annuler', exact: true }).click();
  expect(await (await page.request.get('/api/project')).json()).toEqual(original);
});

test('la fusion par identifiant conserve les champs absents et refuse de changer le contrat d’un tag utilisé', async ({ page }) => {
  const original = await fixture(page);
  let modal = await openPaste(page, 'id;Nom;Sens;Type;Unité\nkeep;Pression renommée;input;REAL;kPa');
  await modal.getByRole('button', { name: 'Préparer l’aperçu', exact: true }).click();
  await expect(modal.getByRole('region', { name: 'Aperçu des tags collés' }).getByRole('alert')).toContainText("Contrat d'une variable utilisée");
  await expect(modal.getByRole('button', { name: 'Appliquer l’import au brouillon', exact: true })).toBeDisabled();
  await modal.getByRole('button', { name: 'Annuler', exact: true }).click();
  modal = await openPaste(page, 'id;Nom;Sens;Type\nkeep;Pression renommée;input;REAL');
  await modal.getByRole('button', { name: 'Préparer l’aperçu', exact: true }).click();
  await expect(modal.getByRole('region', { name: 'Aperçu des tags collés' })).toContainText('0 ajout(s), 1 modification(s), 0 suppression(s)');
  await modal.getByRole('button', { name: 'Appliquer l’import au brouillon', exact: true }).click();
  const final = await save(page);
  expect(final.tags).toEqual([{ ...original.tags[0], name: 'Pression renommée' }]);
  expect(final.scenarios).toEqual(original.scenarios);
});

test('une nouvelle révision bloque l’application du tableau sans effacer le texte collé', async ({ page }) => {
  await fixture(page);
  const text = 'Nom;Sens;Type\nLocal;input;BOOL';
  const modal = await openPaste(page, text);
  await modal.getByRole('button', { name: 'Préparer l’aperçu', exact: true }).click();
  await expect(modal.getByRole('button', { name: 'Appliquer l’import au brouillon', exact: true })).toBeEnabled();
  const projectResponse = await page.request.get('/api/project');
  const project: Project = await projectResponse.json();
  const { token } = await (await page.request.get('/api/session')).json();
  const state = await (await page.request.get('/api/state')).json();
  const response = await page.request.put('/api/project', { headers: { 'X-FAT-Token': token, 'X-FAT-Project-ID': project.id, 'X-FAT-Project-Revision': projectResponse.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': state.run_id ?? '' }, data: { ...project, name: 'Modification dans un autre onglet' } });
  expect(response.ok()).toBeTruthy();
  await expect(modal.getByRole('button', { name: 'Appliquer l’import au brouillon', exact: true })).toBeDisabled();
  await expect(modal.getByRole('textbox', { name: 'Tableau de tags' })).toHaveValue(text);
  expect((await (await page.request.get('/api/project')).json()).tags).toEqual(project.tags);
  await modal.getByRole('button', { name: 'Annuler', exact: true }).click();
});

test('la revue du tableau tient à 768 pixels et se ferme au clavier sans appliquer', async ({ page }, testInfo) => {
  const original = await fixture(page);
  await page.setViewportSize({ width: 768, height: 900 });
  const modal = await openPaste(page, 'Nom\tSens\tType\tValeur initiale\nUn tag dont le nom reste lisible dans la fenêtre\tinput\tREAL\t3');
  await modal.getByRole('button', { name: 'Préparer l’aperçu', exact: true }).click();
  await expect(modal.getByRole('region', { name: 'Aperçu des tags collés' })).toBeVisible();
  expect(await modal.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  expect((await modal.boundingBox())!.width).toBeGreaterThan(650);
  await page.screenshot({ path: testInfo.outputPath('collage-tags-768.png') });
  await modal.getByRole('button', { name: 'Appliquer l’import au brouillon', exact: true }).focus();
  await page.keyboard.press('Tab');
  expect(await modal.evaluate(element => element.contains(document.activeElement))).toBe(true);
  await page.keyboard.press('Escape');
  await expect(modal).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Coller des tags Excel', exact: true })).toBeFocused();
  expect(await (await page.request.get('/api/project')).json()).toEqual(original);
});

test('un fichier Excel UTF-16 conserve les accents et un encodage invalide ne remplace pas le tableau', async ({ page }) => {
  const original = await fixture(page);
  await page.getByRole('button', { name: 'Coller des tags Excel', exact: true }).click();
  const modal = page.getByRole('dialog', { name: 'Coller des tags Excel', exact: true });
  const text = 'Nom\tSens\tType\tNodeId OPC UA\nPression été\tinput\tREAL\tns=2;s=Pression_ete';
  await modal.getByLabel('Fichier texte du tableau', { exact: true }).setInputFiles({ name: 'unicode.tsv', mimeType: 'text/tab-separated-values', buffer: Buffer.from('\ufeff' + text, 'utf16le') });
  await expect(modal.getByRole('textbox', { name: 'Tableau de tags' })).toHaveValue(text);
  await modal.getByRole('button', { name: 'Analyser le tableau', exact: true }).click();
  await modal.getByRole('button', { name: 'Préparer l’aperçu', exact: true }).click();
  await expect(modal.getByRole('region', { name: 'Aperçu des tags collés' })).toContainText('Pression été');
  await expect(modal.getByRole('region', { name: 'Aperçu des tags collés' })).toContainText('ns=2;s=Pression_ete');
  await modal.getByLabel('Fichier texte du tableau', { exact: true }).setInputFiles({ name: 'invalid.csv', mimeType: 'text/csv', buffer: Buffer.from([0xc3, 0x28]) });
  await expect(modal.getByRole('alert')).toContainText('Encodage illisible');
  await expect(modal.getByRole('textbox', { name: 'Tableau de tags' })).toHaveValue(text);
  await expect(modal.getByRole('button', { name: 'Appliquer l’import au brouillon', exact: true })).toBeDisabled();
  await modal.getByRole('button', { name: 'Annuler', exact: true }).click();
  expect(await (await page.request.get('/api/project')).json()).toEqual(original);
});

test('un sens commun explicite complète une liste de noms et types sans modifier le fichier source', async ({ page }) => {
  await fixture(page);
  const modal = await openPaste(page, 'Nom\tType\tAdresse Siemens\nRunning\tBOOL\t%I0.0\nLevel\tREAL\t%IW264');
  const common = modal.getByRole('combobox', { name: 'Sens commun à toutes les lignes', exact: true });
  await expect(common).toHaveValue('');
  await expect(modal.getByRole('button', { name: 'Préparer l’aperçu', exact: true })).toBeDisabled();
  await common.selectOption('input');
  await modal.getByRole('button', { name: 'Préparer l’aperçu', exact: true }).click();
  await expect(modal.getByRole('region', { name: 'Aperçu des tags collés' })).toContainText('2 ajout(s)');
  await modal.getByRole('button', { name: 'Appliquer l’import au brouillon', exact: true }).click();
  const final = await save(page);
  expect(final.tags.slice(1).map(tag => [tag.direction, tag.data_type, tag.writable, tag.node_id])).toEqual([['input', 'BOOL', false, ''], ['input', 'REAL', false, '']]);
});
