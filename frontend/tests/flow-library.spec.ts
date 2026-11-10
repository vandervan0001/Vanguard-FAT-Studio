import { expect, test, type Page } from '@playwright/test';
import { insertCircuit } from '../src/processCircuits';
import { CIRCUIT_LIBRARY_KEY, insertSavedCircuit, makeSavedCircuit } from '../src/circuitLibrary';
import type { CatalogItem, Project } from '../src/types';

async function boot(page: Page) {
  for (const path of ['health', 'project', 'state', 'catalog', 'schema']) expect((await page.request.get(`/api/${path}`)).ok()).toBeTruthy();
  await page.goto('/'); await page.getByLabel('Nom du projet', { exact: true }).waitFor();
  const stop = page.getByRole('button', { name: 'Arrêter l’essai', exact: true });
  if (await stop.isEnabled()) await stop.click();
}
async function blank(page: Page, name = 'Circuits personnels') {
  await boot(page);
  await page.getByRole('button', { name: 'Nouveau', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Nom du projet', { exact: true }).fill(name);
  await page.getByRole('button', { name: 'Créer le projet', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.locator('.palette')).toBeVisible();
  return await (await page.request.get('/api/project')).json() as Project;
}
async function put(page: Page, project: Project) {
  const original = await page.request.get('/api/project'); const active = await original.json();
  const state = await (await page.request.get('/api/state')).json();
  const { token } = await (await page.request.get('/api/session')).json();
  const response = await page.request.put('/api/project', { headers: { 'X-FAT-Token': token, 'X-FAT-Project-ID': active.id, 'X-FAT-Project-Revision': original.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': state.run_id ?? '' }, data: project });
  expect(response.ok(), await response.text()).toBeTruthy(); return await response.json() as Project;
}
async function circuit(page: Page, kind: 'fill' | 'transfer' = 'fill') {
  const project = await blank(page); const catalog: CatalogItem[] = await (await page.request.get('/api/catalog')).json();
  const built = insertCircuit(project, catalog, kind).project;
  for (const item of built.equipment) if (['pump', 'valve_onoff'].includes(item.type)) item.params = { ...item.params, response_s: 0, demo_control: 'constant', demo_command: item.type === 'pump' };
  return { project: built, catalog };
}
async function save(page: Page) {
  const response = page.waitForResponse(response => response.url().endsWith('/api/project') && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  const result = await response; expect(result.ok(), await result.text()).toBeTruthy(); return await result.json() as Project;
}

test('le débit explique une vanne fermée, date la pause et masque un modèle modifié', async ({ page }, testInfo) => {
  const { project } = await circuit(page); const pump = project.equipment.find(item => item.type === 'pump')!;
  await put(page, project); await page.reload();
  await page.getByRole('button', { name: 'Expliquer les débits', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('Démarrez un essai');
  await page.getByRole('dialog').getByRole('button', { name: 'Fermer', exact: true }).click();
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect.poll(async () => Boolean((await (await page.request.get('/api/state')).json()).equipment[pump.id]?.flow_diagnostic)).toBe(true);
  await page.getByRole('button', { name: 'Expliquer les débits', exact: true }).click();
  const modal = page.getByRole('dialog');
  await expect(modal).toContainText('Débit calculé : 0 L/s');
  await expect(modal).toContainText('La vanne est fermée.');
  await expect(modal).toContainText('Commande d’arrêt ou de fermeture reçue.');
  await expect(modal.locator('.flow-device-list article.limiting')).toContainText('XV-101');
  expect(await modal.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('explication-debit.png') });
  await modal.getByRole('button', { name: 'Fermer', exact: true }).click();
  await page.getByRole('button', { name: 'Mettre en pause', exact: true }).click();
  await page.getByRole('button', { name: 'Expliquer les débits', exact: true }).click();
  await expect(modal).toContainText('Essai en pause : dernier cycle calculé');
  await modal.getByRole('button', { name: 'Fermer', exact: true }).click();
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
  await page.getByRole('button', { name: 'Expliquer les débits', exact: true }).click();
  await expect(modal).toContainText('valeurs historiques');
  await modal.getByRole('button', { name: 'Fermer', exact: true }).click();
  await page.getByLabel('Nom du projet', { exact: true }).fill('Brouillon modifié');
  await page.getByRole('button', { name: 'Expliquer les débits', exact: true }).click();
  await expect(modal).toContainText('Le brouillon a changé'); await expect(modal.locator('.flow-summary')).toHaveCount(0);
});

test('un état en erreur ne présente pas les anciens débits comme actuels', async ({ page }) => {
  const { project } = await circuit(page); const pump = project.equipment.find(item => item.type === 'pump')!;
  await put(page, project); await page.reload(); await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect.poll(async () => Boolean((await (await page.request.get('/api/state')).json()).equipment[pump.id]?.flow_diagnostic)).toBe(true);
  await page.route('**/api/state', async route => { const response = await route.fetch(); const data = await response.json(); await route.fulfill({ response, json: { ...data, status: 'error', connection: { ...data.connection, quality: 'bad', connected: false }, error: 'Échange de test interrompu' } }); });
  await page.getByRole('button', { name: 'Expliquer les débits', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('Les anciennes valeurs ne permettent pas', { timeout: 15000 });
  await expect(page.getByRole('dialog').locator('.flow-summary')).toHaveCount(0);
  await page.unroute('**/api/state');
  await page.getByRole('dialog').getByRole('button', { name: 'Fermer', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Arrêter l’essai', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
});

test('enregistrer un circuit et le réutiliser après rechargement dans un autre projet efface ses adresses PLC', async ({ page }, testInfo) => {
  const { project, catalog } = await circuit(page, 'transfer');
  project.tags = project.tags.map((tag, i) => ({ ...tag, node_id: `ns=2;s=Original.${i}`, plc_address: `%M${i}.0`, plc_symbol: `Original.${i}` }));
  const original = await put(page, project); const pump = original.equipment.find(item => item.type === 'pump')!;
  await page.reload(); await page.getByRole('button', { name: 'Construire', exact: true }).click();
  await page.locator(`.react-flow__node[data-id="${pump.id}"]`).click();
  await page.getByRole('button', { name: 'Enregistrer ce circuit', exact: true }).click();
  let modal = page.getByRole('dialog'); await modal.getByLabel('Nom du circuit', { exact: true }).fill('Transfert réutilisable');
  await modal.getByRole('button', { name: 'Enregistrer dans ma bibliothèque', exact: true }).click();
  await expect(modal).toContainText('est enregistré dans votre bibliothèque locale');
  const stored = await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), CIRCUIT_LIBRARY_KEY);
  expect(stored).toHaveLength(1); expect(stored[0].equipment).toHaveLength(4);
  expect(stored[0].tags.every((tag: { node_id: string; plc_address: string; plc_symbol: string }) => !tag.node_id && !tag.plc_address && !tag.plc_symbol)).toBe(true);
  expect(stored[0].plc).toBeUndefined(); expect(stored[0].scenarios).toBeUndefined(); expect(stored[0].runs).toBeUndefined();
  expect(await (await page.request.get('/api/project')).json()).toEqual(original);
  await modal.getByRole('button', { name: 'Fermer', exact: true }).click(); await page.reload();
  const target = await blank(page, 'Autre procédé');
  await page.getByRole('button', { name: 'Mes circuits', exact: true }).click(); modal = page.getByRole('dialog');
  await expect(modal.getByLabel('Contenu du modèle')).toContainText('Transfert réutilisable');
  await modal.getByRole('button', { name: 'Préparer la copie', exact: true }).click();
  await expect(modal).toContainText('Copie vérifiée : 4 équipement(s)');
  await page.screenshot({ path: testInfo.outputPath('bibliotheque-circuit.png') });
  expect(await (await page.request.get('/api/project')).json()).toEqual(target);
  await modal.getByRole('button', { name: 'Appliquer la copie au brouillon', exact: true }).click();
  const inserted = await save(page);
  expect(inserted.plc).toEqual(target.plc); expect(inserted.scenarios).toHaveLength(0);
  expect(inserted.equipment).toHaveLength(4); expect(inserted.tags).toHaveLength(original.tags.length);
  expect(inserted.equipment.every(item => !original.equipment.some(old => old.id === item.id))).toBe(true);
  expect(inserted.tags.every(tag => !tag.node_id && !tag.plc_address && !tag.plc_symbol && !original.tags.some(old => old.id === tag.id))).toBe(true);
  expect(inserted.equipment.every(item => Object.values(item.bindings).every(id => inserted.tags.some(tag => tag.id === id)))).toBe(true);
  const copiedPump = inserted.equipment.find(item => item.type === 'pump')!;
  expect(inserted.equipment.some(item => item.id === copiedPump.params.source_tank_id)).toBe(true);
  expect(inserted.equipment.some(item => item.id === copiedPump.params.tank_id)).toBe(true);
  expect((await (await page.request.get('/api/validate')).json()).valid).toBe(true);
  const saved = makeSavedCircuit(original, catalog, pump.id, 'Second modèle');
  const crowded = { ...target, tags: Array.from({ length: 200 }, (_, i) => ({ ...original.tags[0], id: `filler${i}` })) };
  expect(() => insertSavedCircuit(crowded, catalog, saved)).toThrow('200 tags');
});

test('une bibliothèque corrompue ou un stockage refusé ne modifie ni le projet ni les modèles précédents', async ({ page }) => {
  const project = await blank(page);
  await page.evaluate(key => localStorage.setItem(key, '{not-json'), CIRCUIT_LIBRARY_KEY);
  await page.getByRole('button', { name: 'Mes circuits', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('bibliothèque locale est illisible');
  await expect(page.getByRole('dialog').getByRole('button', { name: 'Préparer la copie', exact: true })).toBeDisabled();
  expect(await page.evaluate(key => localStorage.getItem(key), CIRCUIT_LIBRARY_KEY)).toBe('{not-json');
  expect(await (await page.request.get('/api/project')).json()).toEqual(project);
  await page.getByRole('dialog').getByRole('button', { name: 'Fermer', exact: true }).click();
  await page.evaluate(key => localStorage.removeItem(key), CIRCUIT_LIBRARY_KEY);
  await page.getByRole('button', { name: 'Insérer un circuit de remplissage', exact: true }).click(); const current = await save(page);
  const pump = current.equipment.find(item => item.type === 'pump')!;
  await page.locator(`.react-flow__node[data-id="${pump.id}"]`).click();
  await page.evaluate(key => { const original = Storage.prototype.setItem; Storage.prototype.setItem = function(name, value) { if (name === key) throw new DOMException('quota', 'QuotaExceededError'); return original.call(this, name, value); }; }, CIRCUIT_LIBRARY_KEY);
  await page.getByRole('button', { name: 'Enregistrer ce circuit', exact: true }).click();
  const modal = page.getByRole('dialog'); await modal.getByLabel('Nom du circuit', { exact: true }).fill('Ne pas perdre');
  await modal.getByRole('button', { name: 'Enregistrer dans ma bibliothèque', exact: true }).click();
  await expect(modal.getByRole('alert')).toContainText('Le navigateur ne peut pas enregistrer');
  expect(await page.evaluate(key => localStorage.getItem(key), CIRCUIT_LIBRARY_KEY)).toBeNull();
  expect(await (await page.request.get('/api/project')).json()).toEqual(current);
});

test('la bibliothèque refuse une application périmée et reste accessible au clavier à 768 px', async ({ page }, testInfo) => {
  const { project, catalog } = await circuit(page); const pump = project.equipment.find(item => item.type === 'pump')!;
  const saved = makeSavedCircuit(project, catalog, pump.id, 'Modèle local');
  await page.evaluate(({ key, saved }) => localStorage.setItem(key, JSON.stringify([saved])), { key: CIRCUIT_LIBRARY_KEY, saved });
  await page.setViewportSize({ width: 768, height: 900 });
  await page.getByRole('button', { name: 'Mes circuits', exact: true }).click();
  const modal = page.getByRole('dialog'); await modal.getByRole('button', { name: 'Préparer la copie', exact: true }).click();
  await expect(modal.getByRole('button', { name: 'Appliquer la copie au brouillon', exact: true })).toBeEnabled();
  const bounds = await modal.boundingBox(); expect(bounds!.x).toBeGreaterThanOrEqual(0); expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(768);
  expect(await modal.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('mes-circuits-768.png') });
  const active = await (await page.request.get('/api/project')).json() as Project;
  await put(page, { ...active, name: 'Une autre révision' });
  await expect(modal.getByRole('button', { name: 'Appliquer la copie au brouillon', exact: true })).toBeDisabled({ timeout: 15000 });
  await page.keyboard.press('Escape'); await expect(modal).toHaveCount(0);
  expect((await (await page.request.get('/api/project')).json()).equipment).toHaveLength(0);
});

test('une bibliothèque exportée se restaure dans un autre navigateur sans écraser les modèles existants', async ({ page, browser }, testInfo) => {
  const { project, catalog } = await circuit(page, 'transfer');
  const pump = project.equipment.find(item => item.type === 'pump')!;
  const saved = makeSavedCircuit(project, catalog, pump.id, 'Circuit sauvegardé');
  await page.evaluate(({ key, saved }) => localStorage.setItem(key, JSON.stringify([saved])), { key: CIRCUIT_LIBRARY_KEY, saved });
  await page.getByRole('button', { name: 'Mes circuits', exact: true }).click();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('dialog').getByRole('button', { name: 'Exporter la bibliothèque', exact: true }).click();
  const exported = await downloadPromise; const file = testInfo.outputPath('mes-circuits.json'); await exported.saveAs(file);
  const otherContext = await browser.newContext({ baseURL: new URL(page.url()).origin });
  const other = await otherContext.newPage();
  try {
    await blank(other, 'Bibliothèque restaurée');
    await other.getByRole('button', { name: 'Mes circuits', exact: true }).click();
    const modal = other.getByRole('dialog'); await expect(modal).toContainText('Votre bibliothèque est vide');
    let chooser = other.waitForEvent('filechooser');
    await modal.getByRole('button', { name: 'Importer une bibliothèque', exact: true }).click();
    await (await chooser).setFiles(file);
    await expect(modal.getByLabel('Aperçu de l’import de circuits')).toContainText('1 modèle(s) à ajouter');
    expect(await other.evaluate(key => localStorage.getItem(key), CIRCUIT_LIBRARY_KEY)).toBeNull();
    await modal.getByRole('button', { name: 'Importer ces modèles', exact: true }).click();
    await expect(modal).toContainText('Les modèles sont ajoutés');
    const before = await other.evaluate(key => localStorage.getItem(key), CIRCUIT_LIBRARY_KEY);
    chooser = other.waitForEvent('filechooser');
    await modal.getByRole('button', { name: 'Importer une bibliothèque', exact: true }).click();
    await (await chooser).setFiles({ name: 'incorrect.json', mimeType: 'application/json', buffer: Buffer.from('[{"version":1}]') });
    await expect(modal.getByRole('alert')).toContainText('bibliothèque locale est illisible');
    expect(await other.evaluate(key => localStorage.getItem(key), CIRCUIT_LIBRARY_KEY)).toBe(before);
    chooser = other.waitForEvent('filechooser');
    await modal.getByRole('button', { name: 'Importer une bibliothèque', exact: true }).click();
    await (await chooser).setFiles(file);
    await expect(modal.getByLabel('Aperçu de l’import de circuits')).toContainText('0 modèle(s) à ajouter, 1 déjà présent(s)');
    await modal.getByRole('button', { name: 'Annuler l’import', exact: true }).click();
    await modal.getByRole('button', { name: 'Préparer la copie', exact: true }).click();
    await modal.getByRole('button', { name: 'Appliquer la copie au brouillon', exact: true }).click();
    const result = await save(other); expect(result.equipment).toHaveLength(4); expect(result.tags.every(tag => !tag.node_id)).toBe(true);
  } finally { await otherContext.close(); }
});
