import { expect, test, type APIRequestContext } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import type { Project, Snapshot } from '../src/types';

async function mutation(request: APIRequestContext, path: string) {
  const session = await request.get('/api/session');
  const { token } = await session.json();
  return request.post(`/api${path}`, { headers: { 'X-FAT-Token': token }, data: {} });
}

test.beforeEach(async ({ request, page }) => {
  const state: Snapshot = await (await request.get('/api/state')).json();
  if (['running', 'paused', 'error'].includes(state.status)) expect((await mutation(request, '/run/stop')).ok()).toBeTruthy();
  expect((await mutation(request, '/demo/load')).ok()).toBeTruthy();
  page.on('dialog', dialog => dialog.accept());
  await page.goto('/');
  await expect(page.getByLabel('Nom du projet')).toHaveValue('TK-101 · Banc de remplissage');
  await page.getByRole('button', { name: 'Connexion', exact: true }).click();
});

test('la version TIA sélectionnée persiste, suit le projet exporté et revient à l’import', async ({ page, request }, testInfo) => {
  const version = page.getByRole('combobox', { name: 'Version du projet TIA', exact: true });
  const save = page.getByRole('button', { name: 'Enregistrer', exact: true });
  await expect(version).toHaveValue('V21');
  await version.selectOption('V20');
  await save.click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  await page.reload();
  await page.getByRole('button', { name: 'Connexion', exact: true }).click();
  await expect(version).toHaveValue('V20');
  const stored: Project = await (await request.get('/api/project')).json();
  expect(stored.plc.tia_version).toBe('V20');

  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Exporter', exact: true }).click();
  const file = await downloaded;
  const json = await readFile((await file.path())!, 'utf8');
  expect((JSON.parse(json) as Project).plc.tia_version).toBe('V20');

  await version.selectOption('V21');
  await save.click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  await expect.poll(async () => ((await (await request.get('/api/project')).json()) as Project).plc.tia_version).toBe('V21');
  await page.locator('input[type="file"][accept=".json,application/json"]').setInputFiles({
    name: 'tia-v20.json', mimeType: 'application/json', buffer: Buffer.from(json),
  });
  await expect(page.getByRole('status')).toContainText('Projet importé');
  await page.getByRole('button', { name: 'Connexion', exact: true }).click();
  await expect(version).toHaveValue('V20');
  await expect.poll(async () => ((await (await request.get('/api/project')).json()) as Project).plc.tia_version).toBe('V20');

  await page.getByText('Assistance TIA par Claude Code / Codex', { exact: true }).click();
  const help = page.locator('.help-details').filter({ hasText: 'Assistance TIA par Claude Code / Codex' });
  await expect(help).toContainText('.ap20');
  await expect(help).toContainText('-TiaVersion V20');
  await page.screenshot({ path: testInfo.outputPath('tia-version-v20.png'), fullPage: true });
  await version.selectOption('V21');
  await expect(help).toContainText('.ap21');
  await expect(help).toContainText('-TiaVersion V21');
});

test('la version TIA est verrouillée pendant un essai', async ({ page }) => {
  const version = page.getByRole('combobox', { name: 'Version du projet TIA', exact: true });
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  await expect(version).toBeDisabled();
  await page.getByRole('button', { name: 'Mettre en pause', exact: true }).click();
  await expect(version).toBeDisabled();
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
  await expect(version).toBeEnabled();
});
