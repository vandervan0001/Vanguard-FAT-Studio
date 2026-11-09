import { expect, test, type Page } from '@playwright/test';
import type { CatalogItem, Project, Tag } from '../src/types';

async function fixture(page: Page, opcua = false, duplicateEquipment = false) {
  for (const path of ['health', 'project', 'state', 'catalog', 'schema']) expect((await page.request.get(`/api/${path}`)).ok()).toBeTruthy();
  const { token } = await (await page.request.get('/api/session')).json();
  const before = await page.request.get('/api/project');
  const state = await (await page.request.get('/api/state')).json();
  let headers = { 'X-FAT-Token': token, 'X-FAT-Project-ID': (await before.json()).id, 'X-FAT-Project-Revision': before.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': state.run_id ?? '' };
  if (['running', 'paused', 'error'].includes(state.status)) expect((await page.request.post('/api/run/stop', { headers })).ok()).toBeTruthy();
  const created = await page.request.post('/api/projects', { headers, data: { name: 'Tags · revue isolée' } });
  expect(created.ok(), await created.text()).toBeTruthy();
  const project: Project = await created.json();
  const current = await page.request.get('/api/project');
  const nextState = await (await page.request.get('/api/state')).json();
  headers = { ...headers, 'X-FAT-Project-ID': project.id, 'X-FAT-Project-Revision': current.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': nextState.run_id ?? '' };
  const catalog: CatalogItem[] = await (await page.request.get('/api/catalog')).json();
  const tag = (id: string, name: string, direction: Tag['direction']): Tag => ({ id, name, direction, data_type: 'BOOL', unit: '', initial_value: false, min: null, max: null, node_id: '', writable: direction === 'input' });
  project.tags = [tag('command', 'P101_RunCommand', 'output'), tag('feedback', 'P101_Running', 'input'), tag('fault', 'P101_Fault', 'input'), tag('request', 'P101_Request', 'input'), tag('unrelated', 'Variable conservée', 'input')];
  project.equipment = [{ id: 'mapping_pump', type: 'pump', name: 'P-101', description: '', unit: '', position: { x: 100, y: 100 }, params: { ...catalog.find(item => item.type === 'pump')!.default_params }, bindings: {} }];
  if (duplicateEquipment) project.equipment.push({ ...project.equipment[0], id: 'second_pump', position: { x: 400, y: 100 }, bindings: {} });
  if (opcua) project.plc = { ...project.plc, mode: 'opcua', endpoint: 'opc.tcp://127.0.0.1:4840', approved_virtual_target: 'Fixture metadata', expected_application_uri: 'urn:metadata' };
  const persisted = await page.request.put('/api/project', { headers, data: project });
  expect(persisted.ok(), await persisted.text()).toBeTruthy();
  await page.goto('/');
  await page.getByLabel('Nom du projet', { exact: true }).waitFor();
  const resume = page.getByRole('button', { name: /Reprendre mon projet/ });
  if (await resume.isVisible()) await resume.click();
  await page.getByRole('button', { name: /^Variables & mapping/ }).click();
  return persisted.json() as Promise<Project>;
}

async function saved(page: Page): Promise<Project> {
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.locator('.project-subtitle')).toContainText('Enregistré');
  return (await page.request.get('/api/project')).json();
}

function csv(tags: Tag[]) {
  const fields = ['id', 'name', 'direction', 'data_type', 'unit', 'initial_value', 'min', 'max', 'node_id', 'writable'] as const;
  return fields.join(',') + '\n' + tags.map(tag => fields.map(field => { const value = tag[field] == null ? '' : String(tag[field]); return '"' + value.replaceAll('"', '""') + '"'; }).join(',')).join('\n') + '\n';
}

async function openCsv(page: Page, content: string) {
  await page.locator('input[type=file][accept=".csv,text/csv"]').setInputFiles({ name: 'mapping.csv', mimeType: 'text/csv', buffer: Buffer.from(content) });
  const modal = page.getByRole('dialog', { name: 'Relire l’import des variables' });
  await expect(modal.getByRole('status')).toContainText('ajout(s)');
  return modal;
}

test('la revue globale propose tous les rôles, annule puis applique un seul brouillon', async ({ page }, testInfo) => {
  const original = await fixture(page);
  await page.getByRole('button', { name: 'Revoir toutes les liaisons aux tags', exact: true }).click();
  let modal = page.getByRole('dialog', { name: 'Revoir les liaisons aux tags' });
  await modal.getByRole('button', { name: 'Proposer pour tous les équipements', exact: true }).click();
  await expect(modal.getByRole('status')).toContainText('4 association(s)');
  await expect(modal.locator('.global-binding-summary')).toContainText('1 / 1 rôles requis associés');
  await modal.getByRole('button', { name: 'Annuler', exact: true }).click();
  expect((await (await page.request.get('/api/project')).json()).equipment).toEqual(original.equipment);
  await page.getByRole('button', { name: 'Revoir toutes les liaisons aux tags', exact: true }).click();
  modal = page.getByRole('dialog', { name: 'Revoir les liaisons aux tags' });
  await modal.getByRole('button', { name: 'Proposer pour tous les équipements', exact: true }).click();
  expect((await modal.locator('.binding-picker').boundingBox())!.width).toBeGreaterThan(250);
  expect(await modal.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('revue-globale-tags.png') });
  await modal.getByRole('button', { name: 'Appliquer les liaisons au brouillon', exact: true }).click();
  expect((await (await page.request.get('/api/project')).json()).equipment).toEqual(original.equipment);
  const final = await saved(page);
  expect(final.equipment[0].bindings).toEqual({ command: 'command', feedback: 'feedback', fault: 'fault', manual_request: 'request' });
  expect(final.tags.every(tag => tag.node_id === '')).toBe(true);
});

test('la fusion CSV présente les changements et conserve les variables absentes du fichier', async ({ page }) => {
  const original = await fixture(page);
  const incoming = { ...original.tags[0], name: 'Commande renommée' };
  let modal = await openCsv(page, csv([incoming]));
  await expect(modal).toContainText('1 modification(s), 0 suppression(s)');
  await modal.getByRole('button', { name: 'Annuler', exact: true }).click();
  expect((await (await page.request.get('/api/project')).json()).tags).toEqual(original.tags.map(tag => ({ ...tag, plc_address: '', plc_symbol: '', signal: null })));
  modal = await openCsv(page, csv([incoming]));
  await modal.getByRole('button', { name: 'Appliquer l’import au brouillon', exact: true }).click();
  expect((await (await page.request.get('/api/project')).json()).tags[0].name).toBe(original.tags[0].name);
  const final = await saved(page);
  expect(final.tags).toHaveLength(original.tags.length);
  expect(final.tags[0].name).toBe('Commande renommée');
  expect(final.tags.find(tag => tag.id === 'unrelated')?.name).toBe('Variable conservée');
  await page.reload();
  expect((await (await page.request.get('/api/project')).json()).tags[0].name).toBe('Commande renommée');
});

test('la revue globale ne choisit pas un producteur selon l’ordre de deux repères identiques', async ({ page }) => {
  const original = await fixture(page, false, true);
  await page.getByRole('button', { name: 'Revoir toutes les liaisons aux tags', exact: true }).click();
  const modal = page.getByRole('dialog', { name: 'Revoir les liaisons aux tags' });
  await modal.getByRole('button', { name: 'Proposer pour tous les équipements', exact: true }).click();
  await expect(modal.getByRole('status')).toContainText('Repères d’équipements répétés');
  await expect(modal.locator('.global-binding-summary')).toContainText('0 / 2 rôles requis associés');
  await expect(modal.getByRole('button', { name: 'Appliquer les liaisons au brouillon', exact: true })).toBeDisabled();
  expect((await (await page.request.get('/api/project')).json()).equipment).toEqual(original.equipment);
});

test('un CSV incompatible avec un rôle utilisé est expliqué et ne peut pas être appliqué', async ({ page }) => {
  await fixture(page);
  await page.getByRole('button', { name: 'Revoir toutes les liaisons aux tags', exact: true }).click();
  const review = page.getByRole('dialog', { name: 'Revoir les liaisons aux tags' });
  await review.getByRole('button', { name: 'Proposer pour tous les équipements', exact: true }).click();
  await review.getByRole('button', { name: 'Appliquer les liaisons au brouillon', exact: true }).click();
  const original = await saved(page);
  const incompatible: Tag = { ...original.tags[0], direction: 'input', writable: true };
  const modal = await openCsv(page, csv([incompatible]));
  await expect(modal.getByRole('alert')).toContainText('Contrat d’une variable utilisée'.replace('’', "'"));
  await expect(modal.getByRole('button', { name: 'Appliquer l’import au brouillon', exact: true })).toBeDisabled();
  expect(await (await page.request.get('/api/project')).json()).toEqual(original);
});

test('l’explorateur présente la cible et laisse le NodeId intact si le poste refuse la connexion', async ({ page }) => {
  const original = await fixture(page, true);
  await page.getByRole('button', { name: /^P101_RunCommand/ }).click();
  await page.getByRole('button', { name: 'Choisir le NodeId sur le serveur', exact: true }).click();
  const browser = page.getByRole('region', { name: 'Explorateur OPC UA en lecture seule' });
  await expect(browser).toContainText('Fixture metadata @ opc.tcp://127.0.0.1:4840');
  await browser.getByRole('button', { name: 'Parcourir en lecture seule', exact: true }).click();
  await expect(browser.getByRole('alert')).toContainText('politique du poste');
  await browser.getByRole('button', { name: 'Fermer l’explorateur', exact: true }).click();
  expect((await (await page.request.get('/api/project')).json()).tags.map((tag: Tag) => tag.node_id)).toEqual(original.tags.map(tag => tag.node_id));
  expect((await (await page.request.get('/api/state')).json()).write_count).toBe(0);
});

test('la sélection OPC UA filtre les types et droits sans les modifier', async ({ page }, testInfo) => {
  // UI response fixture only; real protocol and zero-write evidence are in test_opcua_browser.py.
  const original = await fixture(page, true);
  await page.route('**/api/opcua/browse', route => route.fulfill({ json: { node_id: 'i=85', offset: 0, more: false, limit: 100, namespace_index: 2, nodes: [
    { node_id: 'ns=2;s=command', name: 'Commande observée', kind: 'variable', data_type: 'BOOL', readable: true, writable: false, selectable: true, reason: '' },
    { node_id: 'ns=2;s=wrong', name: 'Valeur REAL', kind: 'variable', data_type: 'REAL', readable: true, writable: true, selectable: true, reason: '' },
    { node_id: 'i=2258', name: 'Système', kind: 'variable', data_type: null, readable: false, writable: false, selectable: false, reason: 'Namespace système' },
  ] } }));
  await page.getByRole('button', { name: /^P101_RunCommand/ }).click();
  await page.getByRole('button', { name: 'Choisir le NodeId sur le serveur', exact: true }).click();
  const browser = page.getByRole('region', { name: 'Explorateur OPC UA en lecture seule' });
  await browser.getByRole('button', { name: 'Parcourir en lecture seule', exact: true }).click();
  await expect(browser.getByRole('button', { name: 'Utiliser Valeur REAL', exact: true })).toBeDisabled();
  await expect(browser.getByRole('button', { name: 'Utiliser Système', exact: true })).toBeDisabled();
  await page.screenshot({ path: testInfo.outputPath('explorateur-metadonnees-fixture.png') });
  await browser.getByRole('button', { name: 'Utiliser Commande observée', exact: true }).click();
  expect((await (await page.request.get('/api/project')).json()).tags[0].node_id).toBe('');
  const final = await saved(page);
  expect(final.tags[0]).toMatchObject({ node_id: 'ns=2;s=command', writable: false, direction: 'output', data_type: 'BOOL' });
  expect(final.tags.slice(1).map(tag => tag.node_id)).toEqual(original.tags.slice(1).map(tag => tag.node_id));
});

test('la revue globale conserve la sélection après une perte de connexion et tient à 768 pixels', async ({ page }) => {
  await fixture(page);
  await page.setViewportSize({ width: 768, height: 900 });
  await page.getByRole('button', { name: 'Revoir toutes les liaisons aux tags', exact: true }).click();
  const modal = page.getByRole('dialog', { name: 'Revoir les liaisons aux tags' });
  await modal.getByRole('button', { name: 'Proposer pour tous les équipements', exact: true }).click();
  expect(await modal.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  await page.context().setOffline(true);
  await expect(modal.getByRole('button', { name: 'Appliquer les liaisons au brouillon', exact: true })).toBeDisabled({ timeout: 15_000 });
  await expect(modal.locator('.global-binding-summary')).toContainText('1 / 1 rôles requis associés');
  await page.context().setOffline(false);
  await page.keyboard.press('Escape');
  await expect(modal).toHaveCount(0);
});
