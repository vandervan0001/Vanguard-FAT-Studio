import { expect, test, type Page } from '@playwright/test';
import { duplicateEquipment, insertCircuit, planTransfer } from '../src/processCircuits';
import type { CatalogItem, Project } from '../src/types';

async function newProject(page: Page) {
  for (const path of ['health', 'project', 'state', 'catalog', 'schema']) expect((await page.request.get(`/api/${path}`)).ok()).toBeTruthy();
  await page.goto('/');
  await page.getByLabel('Nom du projet', { exact: true }).waitFor();
  const stop = page.getByRole('button', { name: 'Arrêter l’essai', exact: true });
  if (await stop.isEnabled()) await stop.click();
  await page.getByRole('button', { name: 'Nouveau', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Nom du projet', { exact: true }).fill('Circuits · essai isolé');
  await page.getByRole('button', { name: 'Créer le projet', exact: true }).click();
  await expect(page.locator('.palette')).toBeVisible();
  return await (await page.request.get('/api/project')).json() as Project;
}
async function save(page: Page) {
  const saved = page.waitForResponse(response => response.url().endsWith('/api/project') && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  const response = await saved; expect(response.ok(), await response.text()).toBeTruthy();
  return await response.json() as Project;
}
async function putProject(page: Page, project: Project) {
  const response = await page.request.get('/api/project');
  const active = await response.json();
  const state = await (await page.request.get('/api/state')).json();
  const { token } = await (await page.request.get('/api/session')).json();
  const result = await page.request.put('/api/project', { headers: { 'X-FAT-Token': token, 'X-FAT-Project-ID': active.id, 'X-FAT-Project-Revision': response.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': state.run_id ?? '' }, data: project });
  expect(result.ok(), await result.text()).toBeTruthy();
  return await result.json() as Project;
}

test('un modèle de transfert conserve le volume entre deux cuves et propose une trame sans verdict', async ({ page }, testInfo) => {
  await newProject(page);
  await page.getByRole('button', { name: 'Circuits et transferts', exact: true }).click();
  const modal = page.getByRole('dialog');
  await modal.getByLabel('Ajouter une trame FAT à relire').check();
  await expect(modal.getByLabel('Aperçu du circuit')).toContainText('4 équipement(s) et 17 tag(s)');
  await page.screenshot({ path: testInfo.outputPath('modele-transfert.png') });
  await modal.getByRole('button', { name: 'Appliquer le circuit', exact: true }).click();
  const project = await save(page);
  expect(project.equipment).toHaveLength(4); expect(project.tags).toHaveLength(17); expect(project.connections).toHaveLength(3);
  expect(project.scenarios[0].fat_steps).toHaveLength(3);
  expect(project.scenarios[0].fat_steps!.every(step => step.actions.length === 0 && step.checks.length === 0)).toBe(true);
  expect(project.tags.every(tag => tag.node_id === '')).toBe(true);
  const tanks = project.equipment.filter(item => item.type === 'tank');
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect.poll(async () => (await (await page.request.get('/api/state')).json()).equipment[tanks[1].id]?.level).toBeGreaterThan(26);
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
  const state = await (await page.request.get('/api/state')).json();
  expect(state.equipment[tanks[0].id].level).toBeLessThan(65);
  expect(state.equipment[tanks[0].id].volume_l + state.equipment[tanks[1].id].volume_l).toBeCloseTo(900, 7);
  expect(state.result.verdict).toBe('not_evaluated');
  await page.reload();
  expect((await (await page.request.get('/api/project')).json()).equipment).toEqual(project.equipment);
});

test('relier les équipements prépare ensemble les conduites et le modèle puis conserve les associations', async ({ page }, testInfo) => {
  await newProject(page);
  await page.getByRole('button', { name: 'Insérer un circuit de remplissage', exact: true }).click();
  await page.locator('.palette').getByRole('button', { name: 'Cuve', exact: true }).click();
  const before = await save(page);
  const source = before.equipment.find(item => item.name === 'TK-102')!;
  const target = before.equipment.find(item => item.name === 'TK-101')!;
  const pump = before.equipment.find(item => item.type === 'pump')!;
  const valve = before.equipment.find(item => item.type === 'valve_onoff')!;
  await page.getByRole('button', { name: 'Circuits et transferts', exact: true }).click();
  const modal = page.getByRole('dialog');
  await modal.getByRole('button', { name: 'Relier mes équipements', exact: true }).click();
  await modal.getByLabel('Source du transfert', { exact: true }).selectOption(source.id);
  await modal.getByLabel('Destination du transfert', { exact: true }).selectOption(target.id);
  await expect(modal.getByLabel('Aperçu du circuit')).toContainText('2 conduite(s) graphique(s)');
  expect(await (await page.request.get('/api/project')).json()).toEqual(before);
  expect((await modal.getByLabel('Source du transfert', { exact: true }).boundingBox())!.width).toBeGreaterThan(130);
  expect(await modal.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('transfert-existant.png') });
  await modal.getByRole('button', { name: 'Appliquer le circuit', exact: true }).click();
  expect(await (await page.request.get('/api/project')).json()).toEqual(before);
  const after = await save(page);
  expect(after.tags).toEqual(before.tags);
  const changed = after.equipment.filter(item => [pump.id, valve.id].includes(item.id));
  expect(changed.every(item => item.params.source_tank_id === source.id && item.params.tank_id === target.id && item.params.role === 'inlet')).toBe(true);
  expect(changed[0].params.flow_group).toEqual(changed[1].params.flow_group);
  expect(changed.map(item => item.bindings)).toEqual([pump.bindings, valve.bindings]);
  expect(after.connections.map(line => [line.source, line.target])).toEqual([[source.id, pump.id], [pump.id, valve.id], [valve.id, target.id]]);
});

test('le constructeur refuse une boucle, un circuit partiel et une application après conflit', async ({ page }) => {
  await newProject(page);
  await page.getByRole('button', { name: 'Insérer un circuit de remplissage', exact: true }).click();
  const before = await save(page);
  const tank = before.equipment.find(item => item.type === 'tank')!;
  await page.getByRole('button', { name: 'Circuits et transferts', exact: true }).click();
  const modal = page.getByRole('dialog');
  await modal.getByRole('button', { name: 'Relier mes équipements', exact: true }).click();
  await modal.getByLabel('Source du transfert', { exact: true }).selectOption(tank.id);
  await expect(modal.getByRole('alert')).toContainText('deux cuves différentes');
  await expect(modal.getByRole('button', { name: 'Appliquer le circuit' })).toBeDisabled();
  await modal.getByLabel('Source du transfert', { exact: true }).selectOption('');
  await modal.getByLabel('Inclure XV-101', { exact: true }).uncheck();
  await expect(modal.getByRole('alert')).toContainText('Ajoutez aussi XV-101');
  await modal.getByLabel('Inclure XV-101', { exact: true }).check();
  await expect(modal.getByRole('button', { name: 'Appliquer le circuit' })).toBeEnabled();
  await putProject(page, { ...before, name: 'Changé dans un autre onglet' });
  await expect(modal.getByRole('button', { name: 'Appliquer le circuit' })).toBeDisabled({ timeout: 15000 });
  await modal.getByRole('button', { name: 'Annuler', exact: true }).click();
  const actual = await (await page.request.get('/api/project')).json();
  expect(actual.equipment).toEqual(before.equipment); expect(actual.connections).toEqual(before.connections);
});

test('dupliquer un circuit produit des tags locaux distincts et conserve les références physiques internes', async ({ page }) => {
  const blank = await newProject(page);
  const catalog: CatalogItem[] = await (await page.request.get('/api/catalog')).json();
  const fixture = insertCircuit(blank, catalog, 'transfer').project;
  fixture.tags = fixture.tags.map((tag, index) => ({ ...tag, node_id: `ns=2;s=PLC.Tag${index}`, plc_symbol: `Original.Tag${index}`, plc_address: `%M${index}.0` }));
  const canonical = await putProject(page, fixture); await page.reload();
  await page.getByRole('button', { name: 'Construire', exact: true }).click();
  const pump = fixture.equipment.find(item => item.type === 'pump')!;
  await page.locator(`.react-flow__node[data-id="${pump.id}"]`).click();
  await page.getByRole('button', { name: 'Dupliquer cet équipement ou son circuit', exact: true }).click();
  const modal = page.getByRole('dialog');
  await expect(modal.getByLabel('Aperçu du circuit')).toContainText('4 équipement(s) et 17 tag(s)');
  await modal.getByRole('button', { name: 'Appliquer la copie', exact: true }).click();
  const after = await save(page);
  expect(after.equipment.slice(0, 4)).toEqual(canonical.equipment);
  expect(after.tags.slice(0, 17)).toEqual(canonical.tags);
  const copied = after.equipment.slice(4); const copiedTags = after.tags.slice(17);
  expect(new Set(after.equipment.map(item => item.name)).size).toBe(8);
  expect(copiedTags.every(tag => tag.node_id === '' && tag.plc_symbol === '' && tag.plc_address === '')).toBe(true);
  expect(copied.every(item => Object.values(item.bindings).every(id => copiedTags.some(tag => tag.id === id)))).toBe(true);
  const copiedPump = copied.find(item => item.type === 'pump')!;
  expect(copied.some(item => item.id === copiedPump.params.tank_id)).toBe(true);
  expect(copied.some(item => item.id === copiedPump.params.source_tank_id)).toBe(true);
  expect(copiedPump.params.flow_group).not.toBe(pump.params.flow_group);
  expect(after.connections.slice(3).every(line => copied.some(item => item.id === line.source) && copied.some(item => item.id === line.target))).toBe(true);
});

test('les modèles se composent sans remplacer les données et respectent les limites du projet', async ({ page }) => {
  const blank = await newProject(page);
  const catalog: CatalogItem[] = await (await page.request.get('/api/catalog')).json();
  let project = blank;
  for (const kind of ['fill', 'drain', 'transfer', 'vfd'] as const) project = insertCircuit(project, catalog, kind, true).project;
  expect(project.equipment).toHaveLength(12); expect(project.scenarios).toHaveLength(4);
  expect(new Set(project.equipment.map(item => item.name)).size).toBe(12);
  expect(project.plc).toEqual(blank.plc);
  const crowded = { ...project, tags: [...project.tags] };
  while (crowded.tags.length < 200) crowded.tags.push({ ...project.tags[0], id: `padding-${crowded.tags.length}` });
  expect(() => insertCircuit(crowded, catalog, 'fill')).toThrow('200 tags');
  const original = JSON.stringify(crowded);
  expect(() => duplicateEquipment(crowded, catalog, project.equipment[0].id, false)).toThrow('200 tags');
  expect(JSON.stringify(crowded)).toBe(original);
  const pump = project.equipment.find(item => item.type === 'pump')!;
  expect(() => planTransfer(project, catalog, { sourceId: '', targetId: String(pump.params.tank_id), actuatorIds: [pump.id] })).toThrow('partagent le circuit actuel');
});

test('le constructeur reste accessible à 768 px et son annulation ne crée aucun circuit', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 768, height: 900 });
  const original = await newProject(page);
  await page.getByRole('button', { name: 'Circuits et transferts', exact: true }).click();
  const modal = page.getByRole('dialog');
  const bounds = await modal.boundingBox();
  expect(bounds!.x).toBeGreaterThanOrEqual(0); expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(768);
  expect(await modal.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('circuits-768.png') });
  await page.keyboard.press('Escape');
  await expect(modal).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Circuits et transferts', exact: true })).toBeFocused();
  expect(await (await page.request.get('/api/project')).json()).toEqual(original);
});
