import { expect, test, type Page } from '@playwright/test';
import type { Project } from '../src/types';

async function boot(page: Page) {
  for (const path of ['health', 'project', 'state', 'catalog', 'schema']) expect((await page.request.get(`/api/${path}`)).ok()).toBeTruthy();
  await page.goto('/');
  await page.getByLabel('Nom du projet', { exact: true }).waitFor();
  const stop = page.getByRole('button', { name: 'Arrêter l’essai', exact: true });
  if (await stop.isEnabled()) await stop.click();
}

test('l’accueil ouvre une démo guidée isolée, prête à démarrer sans automate', async ({ page }, testInfo) => {
  await boot(page);
  if (!await page.getByRole('button', { name: 'Essayer la démo', exact: true }).isVisible()) await page.getByRole('button', { name: 'Accueil', exact: true }).click();
  await page.screenshot({ path: testInfo.outputPath('accueil.png') });
  await page.getByRole('button', { name: 'Essayer la démo', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Votre premier essai' })).toBeVisible();
  const project: Project = await (await page.request.get('/api/project')).json();
  expect(project.equipment).toHaveLength(3);
  expect(project.plc).toMatchObject({ mode: 'demo', demo_controller: 'manual_lab_v1' });
  expect(project.tags.every(tag => !tag.node_id)).toBe(true);
  expect((await (await page.request.get('/api/state')).json()).status).toBe('idle');
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Arrêter l’essai', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Mettre la pompe en marche', exact: true }).click();
  await page.getByRole('button', { name: 'Ouvrir la vanne', exact: true }).click();
  const tank = project.equipment.find(item => item.type === 'tank')!;
  await expect.poll(async () => (await (await page.request.get('/api/state')).json()).equipment[tank.id].level).toBeGreaterThan(25);
  await page.screenshot({ path: testInfo.outputPath('premier-essai.png') });
  await page.getByRole('button', { name: 'Essayer un défaut moteur', exact: true }).click();
  const pump = project.equipment.find(item => item.type === 'pump')!;
  await expect.poll(async () => (await (await page.request.get('/api/state')).json()).equipment[pump.id].fault).toBe(true);
  await page.getByRole('button', { name: 'Rétablir le moteur', exact: true }).click();
  await expect.poll(async () => (await (await page.request.get('/api/state')).json()).equipment[pump.id].fault).toBe(false);
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
  expect((await (await page.request.get('/api/state')).json()).result.verdict).toBe('not_evaluated');
});

test('un diagnostic ouvre directement le rôle manquant et disparaît après correction du brouillon', async ({ page }) => {
  await boot(page);
  await page.getByRole('button', { name: 'Nouveau', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Nom du projet', { exact: true }).fill('Corrections guidées');
  await page.getByRole('button', { name: 'Créer le projet', exact: true }).click();
  await page.locator('.palette').getByRole('button', { name: 'Pompe', exact: true }).click();
  const readiness = page.getByRole('region', { name: 'Préparer l’essai' });
  await readiness.getByRole('button', { name: /P-101.*Commande marche PLC/ }).click();
  const modal = page.getByRole('dialog', { name: /Lier les tags/ });
  await expect(modal).toBeVisible();
  await modal.getByRole('button', { name: 'Créer un tag BOOL', exact: true }).click();
  await modal.getByRole('button', { name: 'Appliquer au brouillon', exact: true }).click();
  await expect(readiness.getByRole('button', { name: /P-101.*Commande marche PLC/ })).toHaveCount(0);
  expect((await (await page.request.get('/api/project')).json()).equipment).toHaveLength(0);
});

test('annuler, rétablir et récupérer un brouillon ne modifie pas le projet enregistré', async ({ page }) => {
  await boot(page);
  await page.getByRole('button', { name: 'Nouveau', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Nom du projet', { exact: true }).fill('Brouillon récupérable');
  await page.getByRole('button', { name: 'Créer le projet', exact: true }).click();
  await page.getByRole('button', { name: 'Insérer un circuit de remplissage', exact: true }).click();
  await expect(page.locator('.react-flow__node')).toHaveCount(3);
  await page.getByRole('button', { name: 'Annuler la modification', exact: true }).click();
  await expect(page.locator('.react-flow__node')).toHaveCount(0);
  await page.getByRole('button', { name: 'Rétablir la modification', exact: true }).click();
  await expect(page.locator('.react-flow__node')).toHaveCount(3);
  await expect(page.getByText('Brouillon récupérable sur ce navigateur', { exact: true })).toBeVisible();
  page.once('dialog', dialog => dialog.accept());
  await page.reload();
  await page.getByRole('button', { name: 'Reprendre le brouillon', exact: true }).click();
  await expect(page.locator('.react-flow__node')).toHaveCount(3);
  expect((await (await page.request.get('/api/project')).json()).equipment).toHaveLength(0);
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  expect((await (await page.request.get('/api/project')).json()).equipment).toHaveLength(3);
});

test('un brouillon périmé reste téléchargeable et ne remplace pas une révision plus récente', async ({ page }) => {
  await boot(page);
  await page.getByLabel('Nom du projet', { exact: true }).fill('Mon brouillon non publié');
  await expect(page.getByText('Brouillon récupérable sur ce navigateur', { exact: true })).toBeVisible();
  const response = await page.request.get('/api/project');
  const project: Project = await response.json();
  project.name = 'Révision écrite ailleurs';
  const { token } = await (await page.request.get('/api/session')).json();
  const state = await (await page.request.get('/api/state')).json();
  const saved = await page.request.put('/api/project', { headers: { 'X-FAT-Token': token, 'X-FAT-Project-ID': project.id, 'X-FAT-Project-Revision': response.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': state.run_id ?? '' }, data: project });
  expect(saved.ok()).toBe(true);
  page.once('dialog', dialog => dialog.accept());
  await page.reload();
  await expect(page.getByRole('button', { name: 'Reprendre le brouillon', exact: true })).toBeDisabled();
  await expect(page.getByLabel('Nom du projet', { exact: true })).toBeDisabled();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Télécharger le brouillon', exact: true }).click();
  expect((await download).suggestedFilename()).toContain('brouillon-complet');
  await page.getByRole('button', { name: 'Continuer sans reprendre', exact: true }).click();
  await expect(page.getByLabel('Nom du projet', { exact: true })).toHaveValue('Révision écrite ailleurs');
});

test('deux documents conservent des brouillons distincts et ignorer ne supprime pas celui de l’autre', async ({ page, context }) => {
  await boot(page);
  await page.getByLabel('Nom du projet', { exact: true }).fill('Brouillon du premier onglet');
  await expect(page.getByText('Brouillon récupérable sur ce navigateur', { exact: true })).toBeVisible();
  const second = await context.newPage();
  await second.goto('/');
  await second.getByRole('button', { name: 'Continuer sans reprendre', exact: true }).click();
  await second.getByLabel('Nom du projet', { exact: true }).fill('Brouillon du second onglet');
  await expect(second.getByText('Brouillon récupérable sur ce navigateur', { exact: true })).toBeVisible();
  const records = await second.evaluate(() => Object.keys(localStorage).filter(key => key.startsWith('vanguard:draft:1:') && !key.startsWith('vanguard:draft:1:ack:')).map(key => JSON.parse(localStorage.getItem(key)!)));
  expect(records.map(record => record.project.name)).toEqual(expect.arrayContaining(['Brouillon du premier onglet', 'Brouillon du second onglet']));
  expect(new Set(records.map(record => record.tab)).size).toBe(records.length);
});

test('une sauvegarde locale impossible est visible et laisse l’enregistrement serveur disponible', async ({ page }) => {
  await page.addInitScript(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function(key, value) { if (key.startsWith('vanguard:draft:1:')) throw new DOMException('Quota test', 'QuotaExceededError'); return original.call(this, key, value); };
  });
  await boot(page);
  await page.getByLabel('Nom du projet', { exact: true }).fill('Projet malgré quota local');
  await expect(page.getByRole('alert')).toContainText('Le navigateur ne peut pas conserver le brouillon');
  await expect(page.getByText('Brouillon récupérable sur ce navigateur', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  expect((await (await page.request.get('/api/project')).json()).name).toBe('Projet malgré quota local');
});
