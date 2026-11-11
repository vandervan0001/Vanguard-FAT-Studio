import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import type { Equipment, PidDocument, Project, Snapshot, Tag } from '../src/types';

async function headers(request: APIRequestContext) {
  const [session, project, state] = await Promise.all([request.get('/api/session'), request.get('/api/project'), request.get('/api/state')]);
  return { 'X-FAT-Token': (await session.json()).token, 'X-FAT-Project-ID': (await project.json()).id, 'X-FAT-Project-Revision': project.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': (await state.json()).run_id ?? '' };
}
async function snapshot(request: APIRequestContext): Promise<Snapshot> { return (await request.get('/api/state')).json(); }
const equipment = (id: string, type: Equipment['type'], x: number, y: number, params: Equipment['params'] = {}, bindings: Equipment['bindings'] = {}): Equipment => ({ id, type, name: id, description: '', unit: '', position: { x, y }, params, bindings });
const tag = (id: string, direction: Tag['direction'], value: number): Tag => ({ id, name: id, direction, data_type: 'REAL', unit: '%', initial_value: value, min: 0, max: 100, node_id: '', writable: direction === 'input' });

async function fixture(request: APIRequestContext) {
  if (['running', 'paused', 'error'].includes((await snapshot(request)).status)) expect((await request.post('/api/run/stop', { headers: await headers(request), data: {} })).ok()).toBe(true);
  const base: Project = await (await request.get('/api/project')).json();
  const project: Project = { ...base, id: 'ui-thermal-three-way', name: 'Modèles thermiques et trois voies', description: '', pid_document: null, scenarios: [], simulation: { step_ms: 100, speed: 1 }, plc: { ...base.plc, mode: 'demo', demo_controller: 'manual_lab_v1' },
    tags: [tag('commande', 'output', 100), tag('demande', 'input', 100)],
    equipment: [
      equipment('TK_AB', 'tank', 0, 180, { capacity_l: 1000, initial_level_pct: 90 }),
      equipment('TK_A', 'tank', 650, 0, { capacity_l: 1000, initial_level_pct: 10 }),
      equipment('TK_B', 'tank', 650, 400, { capacity_l: 1000, initial_level_pct: 10 }),
      equipment('V3', 'valve_three_way', 300, 180, { common_tank_id: 'TK_AB', branch_a_tank_id: 'TK_A', branch_b_tank_id: 'TK_B', max_flow_l_s: 8, response_s: 0, initial_position_pct: 100, demo_command: 100 }, { command: 'commande', manual_request: 'demande' }),
      equipment('HX', 'heat_exchanger', 1000, 180, { secondary_flow_equipment: 'V3', secondary_flow_field: 'flow_a_l_s' }),
      { ...equipment('DOC', 'pid_symbol', 1000, 500), symbol_kind: 'heat_exchanger' },
    ],
    connections: [
      { id: 'branch-A', source: 'V3', source_port: 'A', target: 'TK_A', label: 'A', directed: true },
      { id: 'branch-B', source: 'V3', source_port: 'B', target: 'TK_B', label: 'B', directed: true },
      { id: 'circuit-S', source: 'V3', source_port: 'A', target: 'HX', target_port: 'secondary_in', label: 'Secondaire', directed: true },
      { id: 'documentary', source: 'V3', source_port: 'AB', target: 'DOC', target_port: 'primary_in', label: 'Documentaire', directed: true },
    ],
  };
  const response = await request.put('/api/project', { headers: await headers(request), data: project });
  expect(response.ok(), await response.text()).toBe(true);
  return project;
}

test.beforeEach(async ({ request, page }) => {
  expect((await request.get('/api/health')).ok()).toBe(true);
  await fixture(request);
  await page.goto('/');
  await expect(page.getByLabel('Nom du projet')).toHaveValue('Modèles thermiques et trois voies');
});

test('configurer les modèles garde cuves, sources de débit, mesures et rotation explicites', async ({ page, request }, testInfo) => {
  await page.getByRole('button', { name: 'Construire', exact: true }).click();
  await expect(page.locator('.palette').getByRole('button', { name: 'Échangeur simulé', exact: true })).toBeVisible();
  await expect(page.locator('.palette').getByRole('button', { name: 'Vanne trois voies simulée', exact: true })).toBeVisible();
  await expect(page.locator('.pid-symbol-palette-item')).toHaveCount(61);
  await page.locator('.react-flow__node[data-id="V3"]').click();
  await expect(page.getByLabel('Cuve commune AB', { exact: true })).toBeVisible();
  const tankOptions = await page.getByLabel('Cuve commune AB', { exact: true }).locator('option').evaluateAll(options => options.map(option => (option as HTMLOptionElement).value));
  expect(tankOptions).toEqual(['', 'TK_AB', 'TK_A', 'TK_B']);
  await page.getByLabel('Fonction', { exact: true }).selectOption('mixing');
  await page.getByLabel('Fonction', { exact: true }).selectOption('diverting');
  await page.getByRole('combobox', { name: 'Rotation du symbole', exact: true }).selectOption('90');
  await page.locator('.react-flow__node[data-id="HX"]').click();
  const source = page.getByLabel('Secondaire : source de débit (facultative)', { exact: true });
  await expect(source).toBeVisible();
  expect(await source.locator('option').evaluateAll(options => options.map(option => (option as HTMLOptionElement).value))).toEqual(['', 'V3']);
  await expect(page.getByLabel('Secondaire : débit de la source', { exact: true })).toHaveValue('flow_a_l_s');
  await expect(page.getByLabel('Secondaire : débit de la source', { exact: true }).locator('option')).toHaveCount(3);
  await page.getByLabel('Secondaire : débit imposé par PLC', { exact: false }).selectOption('commande');
  await expect(page.getByText('Une source de débit est déjà choisie pour ce circuit.', { exact: false })).toBeVisible();
  await page.getByLabel('Secondaire : débit imposé par PLC', { exact: false }).selectOption('');
  await page.getByRole('button', { name: 'Créer les tags manquants', exact: true }).click();
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  const stored: Project = await (await request.get('/api/project')).json();
  const hx = stored.equipment.find(item => item.id === 'HX')!;
  expect(hx.bindings.primary_flow_command).toBeUndefined();
  expect(hx.bindings.secondary_flow_command).toBeUndefined();
  expect(Object.keys(hx.bindings).sort()).toEqual(['heat', 'primary_flow', 'primary_temperature', 'secondary_flow', 'secondary_temperature']);
  expect(stored.equipment.find(item => item.id === 'V3')!.rotation).toBe(90);
  expect(stored.tags.filter(item => Object.values(hx.bindings).includes(item.id)).every(item => item.direction === 'input')).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('physical-configuration.png') });
  await page.reload();
  expect((await (await request.get('/api/project')).json()).equipment.find((item: Equipment) => item.id === 'HX').params.secondary_flow_field).toBe('flow_a_l_s');
});

test('mesures thermiques, débits de branches et défaut explicite suivent le vrai modèle', async ({ page, request }, testInfo) => {
  await page.getByRole('button', { name: 'Connexion', exact: true }).click();
  await expect(page.getByLabel('Contrôleur de démonstration', { exact: true })).toHaveValue('manual_lab_v1');
  await page.getByLabel('Contrôleur de démonstration', { exact: true }).selectOption('tank_level');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  await page.getByRole('button', { name: 'P&ID', exact: true }).click();
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  await expect.poll(async () => (await snapshot(request)).equipment.V3.flow_a_l_s).toBe(8);
  await expect(page.locator('.pipe-core[data-edge-id="branch-A"]')).toHaveAttribute('data-flowing', 'true');
  await expect(page.locator('.pipe-core[data-edge-id="branch-B"]')).toHaveAttribute('data-flowing', 'false');
  await expect(page.locator('.pipe-core[data-edge-id="circuit-S"]')).toHaveAttribute('data-flowing', 'true');
  await expect(page.locator('.pipe-core[data-edge-id="documentary"]')).toHaveAttribute('data-flowing', 'false');
  const hx = page.locator('.react-flow__node[data-id="HX"]');
  await expect(hx.locator('[data-field="primary_outlet_temperature_c"]')).toContainText('°C');
  await expect(hx.locator('[data-field="secondary_outlet_temperature_c"]')).toContainText('°C');
  await expect(hx.locator('[data-field="heat_kw"]')).toContainText('+');
  await page.locator('.analog-control[data-tag="demande"]').getByLabel('Forçage demande', { exact: true }).fill('0');
  await page.locator('.analog-control[data-tag="demande"]').getByRole('button', { name: 'Forcer', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).equipment.V3.flow_b_l_s).toBe(8);
  await expect(page.locator('.pipe-core[data-edge-id="branch-A"]')).toHaveAttribute('data-flowing', 'false');
  await expect(page.locator('.pipe-core[data-edge-id="branch-B"]')).toHaveAttribute('data-flowing', 'true');
  await expect(page.locator('.pipe-core[data-edge-id="circuit-S"]')).toHaveAttribute('data-flowing', 'false');
  await expect(page.locator('.pipe-core[data-edge-id="documentary"]')).toHaveAttribute('data-flowing', 'false');
  await hx.click();
  await expect(page.getByLabel('Perte d’échange thermique (%)')).toHaveValue('50');
  await page.getByLabel('Perte d’échange thermique (%)').fill('');
  await expect(page.getByRole('button', { name: 'Injecter', exact: true })).toBeDisabled();
  await page.getByLabel('Perte d’échange thermique (%)').fill('100');
  await page.getByRole('button', { name: 'Injecter', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).equipment.HX.heat_kw).toBe(0);
  await expect(hx.locator('[data-field="heat_kw"]')).toContainText('+0 kW');
  await hx.screenshot({ path: testInfo.outputPath('physical-hx-readings.png') });
  await page.getByRole('button', { name: 'Lever', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).equipment.HX.ua_effective_kw_k).toBe(5);
});

test('un dessin HX et trois voies reste documentaire jusqu’au choix explicite des modèles', async ({ page, request }) => {
  const document: PidDocument = { format: 'fat-studio/pid', version: '1.0', title: 'Dessin sans paramètres physiques', source_name: '', source_format: 'json', source_sha256: '', pages: [], warnings: [], metadata: {}, connections: [], equipment: ['heat_exchanger', 'valve_three_way'].map((type, index) => ({ id: index ? 'V' : 'E', name: index ? 'V-source' : 'E-source', type, source_tag: '', position: { x: index * 300, y: 0 }, page: 1, confidence: 1, provenance: 'Déclaration documentaire', review_required: true })) };
  await page.getByRole('button', { name: 'Échanges P&ID', exact: true }).click();
  await page.getByLabel('Document P&ID', { exact: true }).setInputFiles({ name: 'drawing.pid.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(document)) });
  await page.getByRole('button', { name: 'Inspecter le document', exact: true }).click();
  await expect(page.getByLabel('Type FAT de E-source')).toHaveValue('pid:heat_exchanger');
  await expect(page.getByLabel('Type FAT de V-source')).toHaveValue('pid:three_way_valve');
  await page.getByLabel('Type FAT de E-source').selectOption('heat_exchanger');
  await page.getByLabel('Type FAT de V-source').selectOption('valve_three_way');
  await expect(page.locator('.pid-model-choice-note')).toContainText('valeurs du catalogue');
  await page.getByLabel('J’ai vérifié les équipements sélectionnés', { exact: false }).check();
  await page.getByRole('button', { name: 'Préparer le brouillon P&ID', exact: true }).click();
  await expect(page.getByLabel('Brouillon P&ID préparé')).toBeVisible();
  await page.getByLabel('Afficher ce nouveau projet dans l’éditeur.', { exact: false }).check();
  await page.getByRole('button', { name: 'Appliquer au brouillon', exact: true }).click();
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  const prepared: Project = await (await request.get('/api/project')).json();
  expect(prepared.equipment.map(item => item.type)).toEqual(['heat_exchanger', 'valve_three_way']);
  expect(prepared.equipment.every(item => Object.keys(item.bindings).length === 0)).toBe(true);
  expect(prepared.tags).toEqual([]);
  expect((await snapshot(request)).write_count).toBe(0);
});
