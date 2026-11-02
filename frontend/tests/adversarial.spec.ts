import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import type { Project, Snapshot } from '../src/types';

async function mutation(request: APIRequestContext, path: string, body: unknown = {}) {
  const { token } = await (await request.get('/api/session')).json();
  return request.post(`/api${path}`, { headers: { 'X-FAT-Token': token }, data: body });
}

async function snapshot(request: APIRequestContext): Promise<Snapshot> {
  const response = await request.get('/api/state');
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function boot(page: Page) {
  await page.goto('/');
  await expect(page.getByLabel('Nom du projet')).toHaveValue('TK-101 · Banc de remplissage');
  await expect(page.locator('.react-flow__node')).toHaveCount(8);
}

test.beforeEach(async ({ request, page }) => {
  const state = await snapshot(request);
  if (['running', 'paused', 'error'].includes(state.status)) expect((await mutation(request, '/run/stop')).ok()).toBeTruthy();
  expect((await mutation(request, '/demo/load')).ok()).toBeTruthy();
  page.on('dialog', dialog => dialog.accept());
});

test('un brouillon de conclusion et de marqueur survit aux changements de section', async ({ page }) => {
  await boot(page);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  await page.getByRole('button', { name: 'Tendances & rapport', exact: true }).click();
  await page.getByRole('combobox', { name: 'Résultat', exact: true }).selectOption('fail');
  await page.getByRole('textbox', { name: 'Observations', exact: true }).fill('Écart à conserver avant approbation.');
  await page.getByLabel('Commentaire de l’essai').fill('Marqueur en cours de rédaction.');
  await page.getByRole('button', { name: 'P&ID', exact: true }).click();
  await page.getByRole('button', { name: 'Tendances & rapport', exact: true }).click();
  await expect(page.getByRole('combobox', { name: 'Résultat', exact: true })).toHaveValue('fail');
  await expect(page.getByRole('textbox', { name: 'Observations', exact: true })).toHaveValue('Écart à conserver avant approbation.');
  await expect(page.getByLabel('Commentaire de l’essai')).toHaveValue('Marqueur en cours de rédaction.');
});

test('une conclusion enregistrée est relue après rechargement et ne devient pas Non évalué', async ({ page, request }) => {
  await boot(page);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('Arrêté');
  const runId = (await snapshot(request)).run_id;
  await page.getByRole('button', { name: 'Tendances & rapport', exact: true }).click();
  await page.getByRole('combobox', { name: 'Résultat', exact: true }).selectOption('fail');
  await page.getByRole('textbox', { name: 'Observations', exact: true }).fill('Mesure de sécurité non conforme.');
  await page.getByRole('button', { name: 'Enregistrer la conclusion', exact: true }).click();
  await expect(page.getByText('Conclusion enregistrée', { exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole('button', { name: 'Tendances & rapport', exact: true }).click();
  await expect(page.getByRole('combobox', { name: 'Résultat', exact: true })).toHaveValue('fail');
  await expect(page.getByRole('textbox', { name: 'Observations', exact: true })).toHaveValue('Mesure de sécurité non conforme.');
  expect((await snapshot(request)).run_id).toBe(runId);
});

test('un ancien polling arrivé après Pause ne remet jamais l’écran en cours', async ({ page }) => {
  await boot(page);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  let captured!: () => void;
  const hasCaptured = new Promise<void>(resolve => { captured = resolve; });
  let release!: () => void;
  const mayRelease = new Promise<void>(resolve => { release = resolve; });
  let delivered!: () => void;
  const hasDelivered = new Promise<void>(resolve => { delivered = resolve; });
  let first = true;
  await page.route('**/api/state', async route => {
    if (!first) { await route.abort(); return; }
    first = false;
    const response = await route.fetch();
    expect((await response.json()).status).toBe('running');
    captured();
    await mayRelease;
    await route.fulfill({ response });
    delivered();
  });
  await hasCaptured;
  await page.getByRole('button', { name: 'Mettre en pause', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En pause');
  release();
  await hasDelivered;
  // Give the deliberately obsolete response time to reach React, before another poll.
  await page.waitForTimeout(100);
  expect(await page.locator('.status-badge').textContent()).toBe('En pause');
  await expect(page.getByRole('button', { name: 'Reprendre', exact: true })).toBeEnabled();
});

test('enregistrer ou valider un projet inchangé conserve l’essai arrêté et ses exports', async ({ page, request }) => {
  await boot(page);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('Arrêté');
  const runId = (await snapshot(request)).run_id;
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  expect((await snapshot(request)).run_id).toBe(runId);
  await page.getByRole('button', { name: 'Connexion', exact: true }).click();
  await page.getByRole('button', { name: 'Valider le projet', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Configuration locale validée');
  expect((await snapshot(request)).run_id).toBe(runId);
  await page.getByRole('button', { name: 'Tendances & rapport', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Rapport FAT', exact: true })).toBeEnabled();
});

test('créer un procédé vide, ses tags, son scénario puis l’importer reproduit le projet', async ({ page, request }) => {
  await boot(page);
  await page.getByRole('button', { name: 'Nouveau', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Nom du projet').fill('Cuve indépendante');
  await page.getByRole('button', { name: 'Créer le projet', exact: true }).click();
  await expect(page.locator('.react-flow__node')).toHaveCount(0);
  await page.locator('.palette').getByRole('button', { name: 'Cuve', exact: true }).click();
  await expect(page.getByLabel('Nom / repère')).toHaveValue('TK-101');
  await page.getByRole('button', { name: 'Créer les tags manquants', exact: true }).click();
  await page.getByLabel('Niveau initial').fill('35');
  await page.getByRole('button', { name: 'Scénarios', exact: true }).click();
  await page.getByRole('button', { name: 'Nouveau scénario', exact: true }).click();
  await page.getByLabel('Durée (s)').fill('1');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  const stored: Project = await (await request.get('/api/project')).json();
  expect(stored.equipment).toHaveLength(1);
  expect(stored.tags).toHaveLength(4);
  expect(stored.scenarios).toHaveLength(1);
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Exporter', exact: true }).click();
  const exported = await readFile((await (await download).path())!, 'utf8');
  expect(JSON.parse(exported)).toEqual(stored);
  await page.locator('input[type="file"][accept=".json,application/json"]').setInputFiles({ name: 'cuve.json', mimeType: 'application/json', buffer: Buffer.from(exported) });
  await expect(page.getByRole('status')).toContainText('Projet importé');
  await page.getByLabel('Scénario', { exact: true }).selectOption(stored.scenarios[0].id);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Terminé', exact: true })).toBeDisabled();
  expect((await snapshot(request)).equipment[stored.equipment[0].id].level).toBe(35);
});

test('une perte de réseau bloque les commandes puis restaure le brouillon au retour du service', async ({ page }) => {
  await boot(page);
  await page.getByLabel('Nom du projet').fill('Brouillon pendant coupure');
  await page.route('**/api/state', route => route.abort());
  await expect(page.locator('.status-badge')).toHaveText('Service indisponible');
  await expect(page.getByRole('button', { name: 'Démarrer', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Enregistrer', exact: true })).toBeDisabled();
  await page.unroute('**/api/state');
  await expect(page.locator('.status-badge')).toHaveText('Prêt');
  await expect(page.getByLabel('Nom du projet')).toHaveValue('Brouillon pendant coupure');
  await expect(page.getByRole('button', { name: 'Enregistrer', exact: true })).toBeEnabled();
});

test('une largeur de 768 px garde les actions du banc nommées et accessibles', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 768, height: 1024 });
  await boot(page);
  await expect(page.getByRole('button', { name: 'Nouveau', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Ouvrir', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Importer', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Exporter', exact: true })).toBeVisible();
  await expect(page.locator('.mode-badge')).toBeVisible();
  await expect(page.locator('.mode-badge')).toContainText('MODE FAT');
  await expect(page.locator('.mode-badge strong')).toBeVisible();
  await expect(page.locator('.mode-badge strong')).toHaveText('DÉMONSTRATION');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath('workbench-768.png') });
  await page.setViewportSize({ width: 1024, height: 768 });
  await expect(page.locator('.mode-badge strong')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath('workbench-1024.png') });
});

test('un brouillon de rapport reste attaché à son essai si un autre onglet redémarre', async ({ page, request }) => {
  await boot(page);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  const firstRun = (await snapshot(request)).run_id;
  await page.getByRole('button', { name: 'Tendances & rapport', exact: true }).click();
  await page.getByRole('textbox', { name: 'Observations', exact: true }).fill('Réserve du premier essai.');
  expect((await mutation(request, '/run/stop')).ok()).toBeTruthy();
  expect((await mutation(request, '/run/start')).ok()).toBeTruthy();
  const secondRun = (await snapshot(request)).run_id;
  expect(secondRun).not.toBe(firstRun);
  await expect(page.getByRole('alert')).toContainText('brouillon appartient à l’essai précédent');
  await expect(page.getByRole('button', { name: 'Enregistrer la conclusion', exact: true })).toBeDisabled();
  await expect(page.getByRole('textbox', { name: 'Observations', exact: true })).toHaveValue('Réserve du premier essai.');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Télécharger le brouillon du rapport', exact: true }).click();
  const recovered = JSON.parse(await readFile((await (await download).path())!, 'utf8'));
  expect(recovered).toMatchObject({ run_id: firstRun, comment: 'Réserve du premier essai.' });
  expect((await snapshot(request)).result.comment).toBe('');
  await page.getByRole('button', { name: 'Afficher l’essai actuel', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Observations', exact: true })).toHaveValue('');
  await expect(page.getByRole('button', { name: 'Enregistrer la conclusion', exact: true })).toBeEnabled();
});

test('une sauvegarde lente de conclusion conserve les modifications saisies pendant la requête', async ({ page, request }) => {
  await boot(page);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  await page.getByRole('button', { name: 'Tendances & rapport', exact: true }).click();
  const comments = page.getByRole('textbox', { name: 'Observations', exact: true });
  await comments.fill('Première version enregistrée.');
  let ready!: () => void;
  const requested = new Promise<void>(resolve => { ready = resolve; });
  let release!: () => void;
  const released = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/result', async route => { ready(); await released; await route.continue(); });
  await page.getByRole('button', { name: 'Enregistrer la conclusion', exact: true }).click();
  await requested;
  await comments.fill('Nouvelle observation encore non enregistrée.');
  release();
  await expect.poll(async () => (await snapshot(request)).result.comment).toBe('Première version enregistrée.');
  await expect(page.getByRole('button', { name: 'Enregistrer la conclusion', exact: true })).toBeEnabled();
  await expect(comments).toHaveValue('Nouvelle observation encore non enregistrée.');
  await expect(page.getByText('Conclusion modifiée, non enregistrée.')).toBeVisible();
  await expect(page.getByText('Conclusion enregistrée', { exact: true })).toHaveCount(0);
});

test('effacer la valeur du forçage ne force pas silencieusement la mesure à zéro', async ({ page, request }) => {
  await boot(page);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  await page.locator('.react-flow__node[data-id="LT101"]').click();
  await page.getByLabel('Forçage LevelPct').fill('');
  await page.getByRole('button', { name: 'Forcer', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Saisissez une valeur');
  expect((await snapshot(request)).tags.level.forced).toBe(false);
});

test('les symboles montrent la pompe sans retour optionnel et la vanne partiellement ouverte', async ({ page, request }) => {
  const project: Project = await (await request.get('/api/project')).json();
  delete project.equipment.find(equipment => equipment.id === 'P101')!.bindings.feedback;
  expect((await mutation(request, '/project/import', project)).ok()).toBeTruthy();
  await boot(page);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).equipment.P101.running).toBe(true);
  await expect(page.locator('.react-flow__node[data-id="P101"] .node-value')).toHaveText('TRUE');
  await expect.poll(async () => Number((await snapshot(request)).equipment.FCV101.position)).toBeGreaterThan(5);
  await expect(page.locator('.react-flow__node[data-id="FCV101"] .node-value')).toHaveClass(/is-active/);
});

test('un mapping CSV exporté se réimporte et une erreur de mapping conserve les associations', async ({ page, request }) => {
  await boot(page);
  await page.getByRole('button', { name: /^Variables & mapping/ }).click();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Exporter CSV', exact: true }).click();
  const csv = await readFile((await (await download).path())!, 'utf8');
  const input = page.locator('input[type="file"][accept=".csv,text/csv"]');
  await input.setInputFiles({ name: 'mapping.csv', mimeType: 'text/csv', buffer: Buffer.from(csv.replaceAll('ns=3;', 'ns=4;')) });
  await expect(page.getByRole('status')).toContainText('Mapping importé et enregistré');
  const stored: Project = await (await request.get('/api/project')).json();
  expect(stored.tags.every(tag => tag.node_id.startsWith('ns=4;'))).toBeTruthy();
  expect(stored.equipment.find(equipment => equipment.id === 'P101')?.bindings.command).toBe('pump_cmd');
  await input.setInputFiles({ name: 'mapping-invalide.csv', mimeType: 'text/csv', buffer: Buffer.from('id,name\nlevel,Mapping invalide') });
  await expect(page.getByRole('alert')).toBeVisible();
  expect((await (await request.get('/api/project')).json()).tags).toEqual(stored.tags);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
});

test('le mapping d’un autre projet ne peut pas être téléchargé pendant une course entre onglets', async ({ page, request }) => {
  await boot(page);
  await page.getByRole('button', { name: /^Variables & mapping/ }).click();
  const downloads: string[] = [];
  page.on('download', download => downloads.push(download.suggestedFilename()));
  await page.route('**/api/mapping', async route => {
    expect((await mutation(request, '/projects', { name: 'Autre projet pendant export' })).ok()).toBeTruthy();
    await route.continue();
  });
  const response = page.waitForResponse('**/api/mapping');
  await page.getByRole('button', { name: 'Exporter CSV', exact: true }).click();
  expect((await response).status()).toBe(409);
  await expect(page.getByRole('alert').filter({ hasText: /projet actif a changé/ }).first()).toBeVisible();
  expect(downloads).toEqual([]);
});

test('un polling bloqué est signalé puis reprend sans perdre le brouillon', async ({ page }) => {
  await boot(page);
  await page.getByLabel('Nom du projet').fill('Brouillon pendant requête bloquée');
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/state', async route => { await gate; await route.abort().catch(() => undefined); });
  try {
    await expect(page.locator('.status-badge')).toHaveText('Service indisponible', { timeout: 8000 });
    await expect(page.getByRole('button', { name: 'Démarrer', exact: true })).toBeDisabled();
  } finally { release(); await page.unroute('**/api/state'); }
  await expect(page.locator('.status-badge')).toHaveText('Prêt');
  await expect(page.getByLabel('Nom du projet')).toHaveValue('Brouillon pendant requête bloquée');
});

test('un brouillon JSON non appliqué reste récupérable après un conflit de projet', async ({ page, request }) => {
  await boot(page);
  await page.getByRole('button', { name: 'Scénarios', exact: true }).click();
  await page.getByRole('button', { name: /01 · Cycle de référence/ }).click();
  const raw = '[{"at_s": 0, "action": "marker", "message": "À finir"}';
  await page.getByLabel('Étapes JSON du scénario').fill(raw);
  expect((await mutation(request, '/projects', { name: 'Autre onglet pendant édition JSON' })).ok()).toBeTruthy();
  await expect(page.getByRole('alert')).toContainText('Le projet actif a changé');
  const download = page.waitForEvent('download');
  await page.getByRole('alert').getByRole('button', { name: 'Télécharger les étapes JSON', exact: true }).click();
  expect(await readFile((await (await download).path())!, 'utf8')).toBe(raw);
  await expect(page.getByLabel('Étapes JSON du scénario')).toHaveValue(raw);
});

test('une association devenue incompatible reste explicite et peut être corrigée', async ({ page }) => {
  await boot(page);
  await page.getByRole('button', { name: /^Variables & mapping/ }).click();
  await page.getByRole('button', { name: /^PumpCmd/ }).click();
  await page.locator('.tag-details').getByRole('combobox', { name: 'Type', exact: true }).selectOption('REAL');
  await page.getByRole('button', { name: 'P&ID', exact: true }).click();
  await page.locator('.react-flow__node[data-id="P101"]').click();
  const binding = page.locator('.binding-field').filter({ hasText: 'Commande marche PLC' });
  await expect(binding.getByRole('combobox')).toHaveValue('pump_cmd');
  await expect(binding.getByRole('combobox')).toHaveAttribute('aria-invalid', 'true');
  await expect(binding).toContainText('Association incompatible');
  await binding.getByRole('combobox').selectOption('inlet_cmd');
  await expect(binding.getByRole('combobox')).toHaveAttribute('aria-invalid', 'false');
  await expect(binding).not.toContainText('Association incompatible');
});

test('une session locale bloquée propose de réessayer et récupère au retour du service', async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/session', async route => { await gate; await route.abort().catch(() => undefined); });
  await page.goto('/');
  try {
    await expect(page.getByRole('button', { name: 'Réessayer', exact: true })).toBeVisible({ timeout: 8000 });
    await expect(page.locator('.boot-error')).toContainText('Le service local ne répond pas');
  } finally { release(); await page.unroute('**/api/session'); }
  await page.getByRole('button', { name: 'Réessayer', exact: true }).click();
  await expect(page.getByLabel('Nom du projet')).toHaveValue('TK-101 · Banc de remplissage');
  await expect(page.locator('.react-flow__node')).toHaveCount(8);
});

test('glisser un symbole, relier ses ports, déplacer et supprimer persiste le vrai graphe', async ({ page, request }) => {
  await boot(page);
  await page.getByRole('button', { name: 'Nouveau', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Nom du projet').fill('Graphe P&ID construit à la souris');
  await page.getByRole('button', { name: 'Créer le projet', exact: true }).click();
  await expect(page.locator('.react-flow__node')).toHaveCount(0);
  await page.locator('.palette').getByRole('button', { name: 'Cuve', exact: true }).click();
  await page.getByRole('button', { name: 'Créer les tags manquants', exact: true }).click();
  const tank = page.locator('.react-flow__node').filter({ hasText: 'TK-101' });
  const tankId = (await tank.getAttribute('data-id'))!;
  await page.locator('.palette').getByRole('button', { name: 'Pompe', exact: true }).dragTo(page.locator('.canvas-area'), { targetPosition: { x: 180, y: 200 } });
  await expect(page.locator('.react-flow__node')).toHaveCount(2);
  const pump = page.locator('.react-flow__node').filter({ hasText: 'P-101' });
  const pumpId = (await pump.getAttribute('data-id'))!;
  await page.getByRole('combobox', { name: /^Cuve associée/ }).selectOption(tankId);
  await page.getByRole('button', { name: 'Créer les tags manquants', exact: true }).click();
  const source = (await pump.locator('.react-flow__handle.source').boundingBox())!;
  const target = (await tank.locator('.react-flow__handle.target').boundingBox())!;
  await page.mouse.move(source.x + source.width / 2, source.y + source.height / 2);
  await page.mouse.down();
  await page.mouse.move(target.x + target.width / 2, target.y + target.height / 2, { steps: 12 });
  await page.mouse.up();
  await expect(page.locator('.react-flow__edge')).toHaveCount(1);
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  const before: Project = await (await request.get('/api/project')).json();
  expect(before.connections[0]).toMatchObject({ source: pumpId, target: tankId });
  const position = before.equipment.find(item => item.id === pumpId)!.position;
  const box = (await pump.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + 15);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 75, box.y + 90, { steps: 10 });
  await page.mouse.up();
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  const moved: Project = await (await request.get('/api/project')).json();
  expect(moved.equipment.find(item => item.id === pumpId)!.position).not.toEqual(position);
  await page.reload();
  await expect(page.locator('.react-flow__node')).toHaveCount(2);
  await expect(page.locator('.react-flow__edge')).toHaveCount(1);
  await page.locator(`.react-flow__node[data-id="${pumpId}"]`).click();
  const name = page.getByLabel('Nom / repère');
  await name.fill('Pompe testX');
  await name.press('Backspace');
  await expect(page.locator('.react-flow__node')).toHaveCount(2);
  await expect(name).toHaveValue('Pompe test');
  await page.locator('.inspector-footer').getByRole('button', { name: 'Supprimer', exact: true }).click();
  await expect(page.locator('.react-flow__node')).toHaveCount(1);
  await expect(page.locator('.react-flow__edge')).toHaveCount(0);
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  const deleted: Project = await (await request.get('/api/project')).json();
  expect(deleted.equipment.map(item => item.id)).toEqual([tankId]);
  expect(deleted.connections).toEqual([]);
  expect(deleted.tags).toHaveLength(7);
});
