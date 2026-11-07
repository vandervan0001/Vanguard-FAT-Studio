import { expect, test, type Page } from '@playwright/test';
import type { CatalogItem, Project, Tag } from '../src/types';

async function startProject(page: Page) {
  for (const path of ['health', 'project', 'state', 'catalog', 'schema']) expect((await page.request.get(`/api/${path}`)).ok()).toBeTruthy();
  await page.goto('/');
  await page.getByLabel('Nom du projet', { exact: true }).waitFor();
  const stop = page.getByRole('button', { name: 'Arrêter l’essai', exact: true });
  if (await stop.isEnabled()) await stop.click();
  await page.getByRole('button', { name: 'Nouveau', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Nom du projet', { exact: true }).fill('Construction et tags · essai isolé');
  await page.getByRole('button', { name: 'Créer le projet', exact: true }).click();
  await expect(page.locator('.palette')).toBeVisible();
}
async function save(page: Page): Promise<Project> {
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  return (await page.request.get('/api/project')).json();
}

test('les ajouts au clic restent séparés et les repères supprimés peuvent être réutilisés sans doublon', async ({ page }) => {
  await startProject(page);
  for (let i = 0; i < 3; i++) await page.locator('.palette').getByRole('button', { name: 'Cuve', exact: true }).click();
  const project = await save(page);
  expect(new Set(project.equipment.map(item => `${item.position.x}:${item.position.y}`)).size).toBe(3);
  expect(project.equipment.map(item => item.name)).toEqual(['TK-101', 'TK-102', 'TK-103']);
  await page.locator(`.react-flow__node[data-id="${project.equipment[1].id}"]`).click();
  page.once('dialog', dialog => dialog.accept());
  await page.locator('.inspector').getByRole('button', { name: 'Supprimer', exact: true }).click();
  await page.locator('.palette').getByRole('button', { name: 'Cuve', exact: true }).click();
  const final = await save(page);
  expect(final.equipment.map(item => item.name)).toEqual(['TK-101', 'TK-103', 'TK-102']);
});

test('le circuit de départ contient les liaisons, les tags et un modèle qui se remplit', async ({ page }, testInfo) => {
  await startProject(page);
  await page.getByRole('button', { name: 'Insérer un circuit de remplissage', exact: true }).click();
  await expect(page.locator('.react-flow__node')).toHaveCount(3);
  await expect(page.locator('.react-flow__edge')).toHaveCount(2);
  const project = await save(page);
  expect(project.equipment).toHaveLength(3); expect(project.tags).toHaveLength(13);
  expect(project.tags.every(tag => tag.node_id === '' && tag.writable === (tag.direction === 'input'))).toBe(true);
  const tank = project.equipment.find(item => item.type === 'tank')!;
  const actuators = project.equipment.filter(item => item.type !== 'tank');
  expect(actuators.map(item => item.params.tank_id)).toEqual([tank.id, tank.id]);
  expect(actuators[0].params.flow_group).toEqual(actuators[1].params.flow_group);
  await page.screenshot({ path: testInfo.outputPath('circuit-depart.png') });
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect.poll(async () => (await (await page.request.get('/api/state')).json()).equipment[tank.id]?.level).toBeGreaterThan(25);
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
  const state = await (await page.request.get('/api/state')).json();
  expect(state.result.verdict).toBe('not_evaluated');
});

async function bindingFixture(page: Page, options: { ambiguous?: boolean; occupied?: boolean; tagCount?: number } = {}) {
  await startProject(page);
  const response = await page.request.get('/api/project');
  const project: Project = await response.json();
  const catalog: CatalogItem[] = await (await page.request.get('/api/catalog')).json();
  const pumpSpec = catalog.find(item => item.type === 'pump')!;
  const tag = (id: string, name: string, direction: Tag['direction'], data_type: Tag['data_type'] = 'BOOL'): Tag => ({
    id, name, direction, data_type, unit: '', initial_value: data_type === 'BOOL' ? false : 0, min: null, max: null, node_id: '', writable: direction === 'input',
  });
  project.tags = [tag('old-command', 'Commande provisoire', 'output'), tag('command', 'P101_RunCommand', 'output'), tag('feedback', 'P101_Running', 'input'), tag('fault', 'P101_Fault', 'input'), tag('request', 'P101_Request', 'input'), tag('incompatible', 'P101_Running_REAL', 'output', 'REAL')];
  project.tags[1].plc_address = '%Q0.0';
  project.equipment = [{ id: 'binding-pump', name: 'P-101', type: 'pump', description: '', unit: '', position: { x: 200, y: 200 }, params: { ...pumpSpec.default_params }, bindings: { command: 'old-command' } }];
  if (options.ambiguous) project.tags.push(tag('second-command', 'P101_RunCommand', 'output'));
  if (options.occupied) project.equipment.push({ id: 'occupied-input', type: 'digital_input', name: 'PB-101', description: '', unit: '', position: { x: 480, y: 200 }, params: { initial_value: false }, bindings: { value: 'feedback' } });
  while (project.tags.length < (options.tagCount ?? 0)) project.tags.push(tag(`extra-${project.tags.length}`, `Variable ${project.tags.length}`, 'output'));
  const state = await (await page.request.get('/api/state')).json();
  const { token } = await (await page.request.get('/api/session')).json();
  const saved = await page.request.put('/api/project', { headers: { 'X-FAT-Token': token, 'X-FAT-Project-ID': project.id, 'X-FAT-Project-Revision': response.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': state.run_id ?? '' }, data: project });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  await page.reload();
  await page.getByRole('button', { name: 'Construire', exact: true }).click();
  await page.locator('.react-flow__node[data-id="binding-pump"]').click();
  await page.getByRole('button', { name: 'Lier les tags automate', exact: true }).click();
  return (await page.request.get('/api/project')).json() as Promise<Project>;
}

test('les propositions de tags se relisent, s’annulent et persistent avec le NodeId saisi', async ({ page }, testInfo) => {
  const original = await bindingFixture(page);
  let modal = page.getByRole('dialog');
  await modal.getByRole('button', { name: 'Non associé', exact: true }).click();
  await modal.getByRole('button', { name: 'Proposer depuis le repère', exact: true }).click();
  await expect(modal.getByRole('status')).toContainText('4 association(s) proposée(s)');
  await modal.getByRole('button', { name: 'Annuler', exact: true }).click();
  expect(await (await page.request.get('/api/project')).json()).toEqual(original);
  await page.getByRole('button', { name: 'Lier les tags automate', exact: true }).click();
  modal = page.getByRole('dialog');
  await modal.getByRole('button', { name: 'Non associé', exact: true }).click();
  await modal.getByRole('button', { name: 'Proposer depuis le repère', exact: true }).click();
  await modal.locator('.binding-address summary').click();
  await expect(modal.getByLabel('NodeId du tag sélectionné')).toHaveValue('');
  await modal.getByLabel('NodeId du tag sélectionné').fill('ns=2;s=PLC.P101_RunCommand');
  await page.screenshot({ path: testInfo.outputPath('liaison-tags.png') });
  await modal.getByRole('button', { name: 'Appliquer au brouillon', exact: true }).click();
  expect(await (await page.request.get('/api/project')).json()).toEqual(original);
  const final = await save(page);
  expect(final.equipment[0].bindings).toEqual({ command: 'command', feedback: 'feedback', fault: 'fault', manual_request: 'request' });
  expect(final.tags.find(tag => tag.id === 'command')).toMatchObject({ node_id: 'ns=2;s=PLC.P101_RunCommand', plc_address: '%Q0.0', direction: 'output', writable: false });
  expect(final.tags.filter(tag => tag.id !== 'command').every(tag => tag.node_id === '')).toBe(true);
  await page.reload(); await page.getByRole('button', { name: 'Construire', exact: true }).click();
  await page.locator('.react-flow__node[data-id="binding-pump"]').click();
  await page.getByRole('button', { name: 'Lier les tags automate', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('button', { name: 'Appliquer au brouillon', exact: true })).toBeDisabled();
});

test('les noms ambigus, types incompatibles et entrées déjà produites ne sont pas associés automatiquement', async ({ page }) => {
  await bindingFixture(page, { ambiguous: true, occupied: true });
  const modal = page.getByRole('dialog');
  await modal.getByRole('button', { name: 'Non associé', exact: true }).click();
  await modal.getByRole('button', { name: 'Proposer depuis le repère', exact: true }).click();
  await expect(modal.locator('.binding-roles').getByRole('button', { name: /^Commande marche PLC/ })).toContainText('À associer');
  await expect(modal.locator('.binding-candidates').getByText('Identifiant : command · %Q0.0', { exact: true })).toBeVisible();
  await expect(modal.locator('.binding-candidates').getByText('Identifiant : second-command', { exact: true })).toBeVisible();
  await modal.locator('.binding-roles').getByRole('button', { name: /^Retour marche simulé/ }).click();
  await expect(modal.locator('.binding-candidates').getByRole('button', { name: /^P101_Running\b/ })).toBeDisabled();
  await expect(modal.locator('.binding-candidates')).not.toContainText('P101_Running_REAL');
  await modal.getByLabel('Rechercher un tag compatible').fill('sans correspondance');
  await expect(modal.getByText('Aucun tag compatible avec cette recherche.', { exact: false })).toBeVisible();
});

test('la revue respecte la limite de tags et conserve son brouillon en cas de perte de connexion', async ({ page }) => {
  const original = await bindingFixture(page, { tagCount: 198 });
  const modal = page.getByRole('dialog');
  await modal.getByRole('button', { name: 'Créer les tags manquants', exact: true }).click();
  await expect(modal.getByRole('status')).toContainText('limité à 200 tags');
  await modal.locator('.binding-roles').getByRole('button', { name: /^Retour marche simulé/ }).click();
  await modal.getByRole('button', { name: 'Créer un tag BOOL', exact: true }).click();
  await expect(modal.getByRole('button', { name: 'Créer un tag BOOL', exact: true })).toBeDisabled();
  await expect(modal.getByRole('button', { name: 'Appliquer au brouillon', exact: true })).toBeEnabled();
  await page.context().setOffline(true);
  await expect(modal.getByRole('button', { name: 'Appliquer au brouillon', exact: true })).toBeDisabled({ timeout: 15_000 });
  await expect(modal.locator('.binding-roles')).toContainText('P-101.feedback');
  await page.context().setOffline(false);
  await modal.getByRole('button', { name: 'Annuler', exact: true }).click();
  expect(await (await page.request.get('/api/project')).json()).toEqual(original);
});

test('tracer une liaison par les noms et choisir une cuve source évite les identifiants internes', async ({ page }) => {
  await startProject(page);
  await page.getByRole('button', { name: 'Insérer un circuit de remplissage', exact: true }).click();
  await page.getByLabel('Rechercher un équipement').fill('cuve');
  await expect(page.locator('.palette-items button')).toHaveCount(1);
  await page.locator('.palette').getByRole('button', { name: 'Cuve', exact: true }).click();
  await page.getByLabel('Rechercher un équipement').fill('');
  const before = await save(page);
  const pump = before.equipment.find(item => item.type === 'pump')!;
  const source = before.equipment.find(item => item.name === 'TK-102')!;
  await page.locator(`.react-flow__node[data-id="${pump.id}"]`).click();
  await page.getByLabel(/^Cuve source du transfert/).selectOption({ label: 'TK-102' });
  await page.getByLabel('Relier à', { exact: true }).selectOption({ label: 'TK-102' });
  await page.getByRole('button', { name: 'Tracer la liaison', exact: true }).click();
  const after = await save(page);
  expect(after.equipment.find(item => item.id === pump.id)?.params.source_tank_id).toBe(source.id);
  expect(after.connections.some(line => line.source === pump.id && line.target === source.id)).toBe(true);
  expect(after.equipment.find(item => item.id === pump.id)?.params.flow_group).toBe(pump.params.flow_group);
});

test('la revue des tags tient dans une fenêtre étroite et se ferme au clavier', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 768, height: 900 });
  await bindingFixture(page);
  const modal = page.getByRole('dialog');
  const bounds = await modal.boundingBox();
  expect(bounds?.x).toBeGreaterThanOrEqual(0); expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(768);
  expect(await modal.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('liaison-tags-768.png') });
  await page.keyboard.press('Escape'); await expect(modal).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Lier les tags automate', exact: true })).toBeFocused();
});
