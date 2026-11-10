import { expect, test, type Page } from '@playwright/test';
import type { Project } from '../src/types';

const target = { id: 'a'.repeat(64), name: 'Banc connu', endpoint: 'opc.tcp://127.0.0.1:4867', expected_application_uri: 'urn:known:fixture', approved_virtual_target: 'Banc connu', server_certificate_sha256: '', security_policy: 'None', authentication_required: false, selectable: true, reason: '' };

async function fixture(page: Page, targets = [target]) {
  for (const path of ['health', 'project', 'state', 'catalog', 'schema']) expect((await page.request.get(`/api/${path}`)).ok()).toBeTruthy();
  const { token } = await (await page.request.get('/api/session')).json();
  const before = await page.request.get('/api/project');
  const state = await (await page.request.get('/api/state')).json();
  let headers = { 'X-FAT-Token': token, 'X-FAT-Project-ID': (await before.json()).id, 'X-FAT-Project-Revision': before.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': state.run_id ?? '' };
  if (['running', 'paused', 'error'].includes(state.status)) expect((await page.request.post('/api/run/stop', { headers })).ok()).toBeTruthy();
  const created = await page.request.post('/api/projects', { headers, data: { name: 'Cibles · projet isolé' } });
  expect(created.ok(), await created.text()).toBeTruthy();
  const project: Project = await created.json();
  headers = { ...headers, 'X-FAT-Project-ID': project.id, 'X-FAT-Project-Revision': created.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': '' };
  project.plc = { ...project.plc, mode: 'opcua', endpoint: 'opc.tcp://127.0.0.1:4840', expected_application_uri: 'urn:old:fixture', approved_virtual_target: 'Ancienne cible', namespace_uri: 'urn:old:namespace', username_env: 'OLD_USER', password_env: 'OLD_PASSWORD', client_certificate: 'old.der', client_private_key: 'old.key' };
  const saved = await page.request.put('/api/project', { headers, data: project });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  await page.route('**/api/connection/targets', route => route.fulfill({ json: { targets, editable_from_browser: false } }));
  await page.route('**/api/connection/targets/preview', async route => {
    const body = route.request().postDataJSON();
    expect(body.target_id).toBe(target.id);
    const next = structuredClone(body.project) as Project;
    next.plc = { ...next.plc, endpoint: target.endpoint, expected_application_uri: target.expected_application_uri, approved_virtual_target: target.name, security_policy: 'None', server_certificate_sha256: '', namespace_uri: '', username_env: '', password_env: '', client_certificate: '', client_private_key: '' };
    next.simulation.speed = 1;
    await route.fulfill({ json: { project: next, target, authentication_required: false, notice: 'La cible est préparée dans le brouillon. Aucune connexion effectuée.' } });
  });
  await page.goto('/');
  await page.getByLabel('Nom du projet', { exact: true }).waitFor();
  const resume = page.getByRole('button', { name: /Reprendre mon projet/ });
  if (await resume.isVisible()) await resume.click();
  await page.getByRole('button', { name: /^Connexion/ }).click();
  await expect(page.getByRole('region', { name: 'Cibles habituelles' })).toBeVisible();
  return project;
}

async function prepare(page: Page) {
  await page.getByLabel('Cible habituelle', { exact: true }).selectOption(target.id);
  await expect(page.getByText('None · réseau virtuel isolé, sans chiffrement', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Préparer cette cible', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Utiliser cette cible dans le brouillon', exact: true })).toBeEnabled();
}

test('la cible connue se relit, s’annule et ne remplace les réglages qu’après application puis enregistrement', async ({ page }, testInfo) => {
  const original = await fixture(page);
  await prepare(page);
  await page.getByRole('button', { name: 'Annuler le choix', exact: true }).click();
  await expect(page.getByLabel('Endpoint OPC UA', { exact: true })).toHaveValue(original.plc.endpoint);
  expect((await (await page.request.get('/api/project')).json()).plc).toEqual(original.plc);
  await prepare(page);
  await page.screenshot({ path: testInfo.outputPath('cible-connue-apercu.png') });
  await page.getByRole('button', { name: 'Utiliser cette cible dans le brouillon', exact: true }).click();
  await expect(page.getByLabel('Endpoint OPC UA', { exact: true })).toHaveValue(target.endpoint);
  await expect(page.getByLabel('Namespace URI (si nécessaire)', { exact: true })).toHaveValue('');
  expect((await (await page.request.get('/api/project')).json()).plc.endpoint).toBe(original.plc.endpoint);
  const save = page.waitForResponse(response => response.url().endsWith('/api/project') && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  expect((await save).ok()).toBeTruthy();
  const stored: Project = await (await page.request.get('/api/project')).json();
  expect(stored.plc).toMatchObject({ endpoint: target.endpoint, expected_application_uri: target.expected_application_uri, approved_virtual_target: target.name, namespace_uri: '', username_env: '', password_env: '', client_certificate: '', client_private_key: '' });
  expect((await (await page.request.get('/api/state')).json()).write_count).toBe(0);
  await page.reload();
  await page.getByLabel('Nom du projet', { exact: true }).waitFor();
  await page.getByRole('button', { name: /^Connexion/ }).click();
  await expect(page.getByLabel('Endpoint OPC UA', { exact: true })).toHaveValue(target.endpoint);
});

test('un aperçu de cible périmé ne remplace pas une modification du projet', async ({ page }) => {
  const original = await fixture(page);
  await prepare(page);
  await page.getByLabel('Nom du projet', { exact: true }).fill('Modification conservée');
  await expect(page.getByRole('button', { name: 'Utiliser cette cible dans le brouillon', exact: true })).toBeDisabled();
  await expect(page.getByRole('alert')).toContainText('Le projet a changé');
  await page.getByRole('button', { name: 'Annuler le choix', exact: true }).click();
  await expect(page.getByLabel('Nom du projet', { exact: true })).toHaveValue('Modification conservée');
  await expect(page.getByLabel('Endpoint OPC UA', { exact: true })).toHaveValue(original.plc.endpoint);
});

test('une cible révoquée reste refusée sans effacer les champs actuels', async ({ page }) => {
  const original = await fixture(page);
  await page.route('**/api/connection/targets/preview', route => route.fulfill({ status: 403, json: { detail: 'Cette cible a changé ou n’est plus autorisée. Actualisez la liste avant de choisir.' } }));
  await page.getByLabel('Cible habituelle', { exact: true }).selectOption(target.id);
  await page.getByRole('button', { name: 'Préparer cette cible', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('n’est plus autorisée');
  await expect(page.getByRole('button', { name: 'Utiliser cette cible dans le brouillon', exact: true })).toHaveCount(0);
  await expect(page.getByLabel('Endpoint OPC UA', { exact: true })).toHaveValue(original.plc.endpoint);
});

test('la vérification reste volontaire et son résultat expire dès que les réglages changent', async ({ page }) => {
  await fixture(page);
  let checks = 0;
  await page.route('**/api/connection/check', async route => {
    checks++;
    const body = route.request().postDataJSON();
    expect(body.confirmation).toBe(`${body.project.plc.approved_virtual_target} @ ${body.project.plc.endpoint}`);
    expect(route.request().headers()['x-fat-project-revision']).toBeTruthy();
    await route.fulfill({ json: { connected: true, identity_verified: true, mapping_checked: false, target: body.confirmation, message: 'Connexion et identité vérifiées, puis session fermée. Le mapping reste à vérifier.' } });
  });
  await prepare(page);
  await page.getByRole('button', { name: 'Utiliser cette cible dans le brouillon', exact: true }).click();
  expect(checks).toBe(0);
  await page.getByRole('button', { name: 'Vérifier la connexion en lecture seule', exact: true }).click();
  await expect(page.getByText('Connexion et identité vérifiées, puis session fermée. Le mapping reste à vérifier.', { exact: true })).toBeVisible();
  expect(checks).toBe(1);
  const state = await (await page.request.get('/api/state')).json();
  expect(state.status).toBe('idle'); expect(state.run_id).toBeNull(); expect(state.write_count).toBe(0);
  await page.getByLabel('Endpoint OPC UA', { exact: true }).fill('opc.tcp://127.0.0.1:4888');
  await expect(page.getByText('Connexion et identité vérifiées, puis session fermée. Le mapping reste à vérifier.', { exact: true })).toHaveCount(0);
});

test('une liste vide explique le prochain geste et reste lisible à 768 pixels', async ({ page }, testInfo) => {
  await fixture(page, []);
  await page.setViewportSize({ width: 768, height: 900 });
  const picker = page.getByRole('region', { name: 'Cibles habituelles' });
  await expect(picker).toContainText('Aucune cible enregistrée sur ce poste');
  await expect(picker).toContainText('fat-studio authorize-target');
  await expect(page.getByLabel('Cible habituelle', { exact: true })).toHaveCount(0);
  expect(await picker.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('cibles-absentes-768.png') });
});
