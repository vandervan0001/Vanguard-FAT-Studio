import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import type { Project, Snapshot } from '../src/types';

async function mutation(request: APIRequestContext, path: string, body: unknown = {}) {
  const { token } = await (await request.get('/api/session')).json();
  return request.post(`/api${path}`, { headers: { 'X-FAT-Token': token }, data: body });
}
async function snapshot(request: APIRequestContext): Promise<Snapshot> { return (await request.get('/api/state')).json(); }
async function boot(page: Page) {
  await page.goto('/');
  const project: Project = await (await page.request.get('/api/project')).json();
  await expect(page.getByLabel('Nom du projet')).toHaveValue(project.name);
  await expect(page.locator('.react-flow__node')).toHaveCount(project.equipment.filter(item => !['digital_input', 'indicator'].includes(item.type)).length);
}

test.beforeEach(async ({ request, page }) => {
  const state = await snapshot(request);
  if (['running', 'paused', 'error'].includes(state.status)) expect((await mutation(request, '/run/stop')).ok()).toBeTruthy();
  expect((await mutation(request, '/pilot/load')).ok()).toBeTruthy();
  page.on('dialog', dialog => dialog.accept());
});

test('le pupitre explique un clic bloqué et distingue les commandes disponibles en pause', async ({ page, request }) => {
  await boot(page);
  const mode = page.locator('.workspace-execution');
  const digital = page.getByRole('button', { name: 'Commutateur P101_Request', exact: true });
  const analog = page.getByLabel('Forçage P101_RequestedSpeed', { exact: true });
  const feedback = page.locator('.io-block-feedback');
  const requests: string[] = [];
  page.on('request', request => {
    if (new URL(request.url()).pathname.startsWith('/api/force')) requests.push(request.method());
  });
  const clickVisibleControl = async (control: typeof digital) => {
    await control.scrollIntoViewIfNeeded();
    const box = (await control.boundingBox())!;
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  };

  const scenario = page.getByLabel('Scénario', { exact: true });
  await scenario.selectOption('demo-fill-source');
  await expect(mode).toHaveText('Scénario automatique · Au repos');
  await scenario.selectOption('demo-guided-io');
  await expect(mode).toHaveText('FAT pas à pas · Au repos');
  await scenario.selectOption('');
  await expect(mode).toHaveText('Essai libre · Au repos');
  await expect(digital).toBeDisabled();
  await clickVisibleControl(digital);
  await expect(feedback).toContainText('Démarrez l’essai');
  await expect(analog).toBeDisabled();
  await clickVisibleControl(analog);
  await expect(feedback.last()).toContainText('Démarrez l’essai');
  expect(requests).toEqual([]);

  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(mode).toHaveText('Essai libre · En cours');
  await expect(feedback).toHaveCount(0);
  await digital.dblclick();
  await expect.poll(async () => (await snapshot(request)).tags.p101_request.value).toBe(true);

  await page.getByRole('button', { name: 'Mettre en pause', exact: true }).click();
  await expect(mode).toHaveText('Essai libre · En pause');
  await page.getByRole('button', { name: 'Tester les I/O', exact: true }).click();
  await expect(digital).toBeDisabled();
  await page.getByRole('button', { name: 'Afficher l’aide pour P101_Request', exact: true }).press('Enter');
  await expect(feedback).toContainText('Reprendre');
  await expect(analog).toBeEnabled();
  await analog.fill('70');
  await page.getByTitle('Forcer P101_RequestedSpeed', { exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).tags.p101_requested_speed.value).toBe(70);
});

test('pupitre complet, symboles vectoriels, impulsion serveur et maintien libéré', async ({ page, request }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await boot(page);
  const project: Project = await (await request.get('/api/project')).json();
  await expect(page.locator('.digital-control')).toHaveCount(project.tags.filter(tag => tag.direction === 'input' && tag.data_type === 'BOOL').length);
  await expect(page.locator('.analog-control')).toHaveCount(project.tags.filter(tag => tag.direction === 'input' && tag.data_type !== 'BOOL').length);
  await expect(page.locator('.analog-control .stimulus-slider')).toHaveCount(project.tags.filter(tag => tag.direction === 'input' && tag.data_type !== 'BOOL').length);
  await expect(page.locator('.digital-push .contact-symbol')).toHaveCount(project.tags.filter(tag => tag.direction === 'input' && tag.data_type === 'BOOL').length);
  await page.screenshot({ path: testInfo.outputPath('pilot-console.png') });
  await page.getByRole('button', { name: 'Construire', exact: true }).click();
  await expect(page.locator('.react-flow__node')).toHaveCount(project.equipment.length);
  await expect(page.locator('.palette')).toBeVisible();
  await page.locator('.palette').getByRole('button', { name: 'Bouton / entrée TOR', exact: true }).click();
  await page.getByLabel('Nom / repère', { exact: true }).fill('PB · Poussoir de test');
  await page.getByRole('button', { name: 'Créer les tags manquants', exact: true }).click();
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  await page.getByRole('button', { name: 'Tester les I/O', exact: true }).click();
  await expect(page.locator('.react-flow__node')).toHaveCount(project.equipment.filter(item => !['digital_input', 'indicator'].includes(item.type)).length);
  await expect(page.locator('.control-pushbutton .contact-symbol')).toHaveCount(1);
  await expect(page.locator('.control-switch .contact-symbol')).toHaveCount(11);
  await expect(page.locator('.control-contact .contact-symbol')).toHaveCount(29);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.editing-locked')).toContainText('I/O de test actives');
  const pulseResponse = page.waitForResponse(response => response.url().endsWith('/api/force/pulse') && response.request().method() === 'POST');
  await page.locator('.digital-control[data-tag="p101_request"] .digital-push').click();
  expect((await pulseResponse).ok()).toBeTruthy();
  await expect.poll(async () => (await snapshot(request)).tags.p101_command.value).toBe(true);
  await expect.poll(async () => (await snapshot(request)).tags.p101_request.forced).toBe(false);
  const pulseCount = (await snapshot(request)).events.filter(event => event.kind === 'pulse').length;
  const stop = page.getByRole('button', { name: 'Contact StopHealthy', exact: true });
  await stop.scrollIntoViewIfNeeded();
  const contact = (await stop.boundingBox())!;
  await page.mouse.click(contact.x + contact.width / 2, contact.y + contact.height / 2, { clickCount: 1 });
  await page.waitForTimeout(400); // The slow second click must cancel the pending single-click impulse.
  await page.mouse.click(contact.x + contact.width / 2, contact.y + contact.height / 2, { clickCount: 2 });
  await expect.poll(async () => (await snapshot(request)).tags.stop_healthy.value).toBe(false);
  await expect.poll(async () => (await snapshot(request)).tags.p101_command.value).toBe(false);
  await expect(page.getByRole('button', { name: 'Libérer le maintien StopHealthy', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Contact StopHealthy', exact: true }).dblclick();
  await expect.poll(async () => (await snapshot(request)).tags.stop_healthy.forced).toBe(false);
  await expect.poll(async () => (await snapshot(request)).tags.stop_healthy.value).toBe(true);
  const end = await snapshot(request);
  expect(end.tags.p101_command.value).toBe(false);
  expect(end.events.filter(event => event.kind === 'pulse')).toHaveLength(pulseCount);
  expect(errors).toEqual([]);
});

test('stimuli analogiques : ingénierie, pourcentage, mA et codes de diagnostic déclarés', async ({ page, request }, testInfo) => {
  await boot(page);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  const input = page.locator('.analog-control[data-tag="lt101_raw"]');
  const unit = input.getByLabel('Unité de stimulus LT101_Raw');
  const value = input.getByLabel('Forçage LT101_Raw');
  await unit.selectOption('engineering');
  await value.fill('50');
  await input.getByRole('button', { name: 'Forcer', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).tags.lt101_raw.value).toBe(13824);
  await input.getByRole('button', { name: 'Préparer 25 % LT101_Raw', exact: true }).click();
  await expect(value).toHaveValue('25');
  await input.getByRole('button', { name: 'Modifier', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).tags.lt101_raw.value).toBe(6912);
  await unit.selectOption('percent');
  await value.fill('75');
  await input.getByRole('button', { name: 'Modifier', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).tags.lt101_raw.value).toBe(20736);
  await value.fill('61.3');
  await input.getByRole('button', { name: 'Modifier', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).tags.lt101_raw.value).toBe(16948);
  await input.getByRole('slider', { name: 'Pourcentage LT101_Raw' }).press('End');
  await expect(value).toHaveValue('100');
  await input.getByRole('button', { name: 'Modifier', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).tags.lt101_raw.value).toBe(27648);
  await unit.selectOption('mA');
  await value.fill('12');
  await input.getByRole('button', { name: 'Modifier', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).tags.lt101_raw.value).toBe(13824);
  await expect(input.getByRole('button', { name: 'Injecter 0 mA', exact: true })).toHaveCount(0);
  await input.getByLabel('Diagnostic hors plage LT101_Raw').check();
  await input.getByRole('button', { name: 'Injecter 0 mA', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).tags.lt101_raw.value).toBe(-32768);
  await expect(input.locator('.conversion-preview')).toContainText('code du profil');
  await expect(input.locator('.analog-reading')).toContainText('Diagnostic bas');
  await expect(input.locator('.analog-reading')).not.toContainText('mA');
  await expect(input.locator('.stimulus-slider > label')).toContainText('hors plage');
  await input.getByRole('button', { name: 'Injecter 24 mA', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).tags.lt101_raw.value).toBe(32767);
  await expect(input.locator('.analog-reading')).toContainText('Diagnostic haut');
  await expect(input.locator('.analog-reading')).not.toContainText('mA');
  await page.screenshot({ path: testInfo.outputPath('analog-diagnostic.png') });
  await input.getByRole('button', { name: 'Libérer LT101_Raw', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).tags.lt101_raw.forced).toBe(false);
});

test('un diagnostic attendu peut être observé conforme sans confondre hors plage et erreur de communication', async ({ page, request }) => {
  const project: Project = await (await request.get('/api/project')).json();
  project.scenarios.push({ id: 'browser-diagnostic', name: 'Diagnostic attendu', execution_mode: 'guided', duration_s: 60, steps: [], fat_steps: [{ id: 'diagnostic-1', name: 'Signal haut hors plage', instructions: 'Observer le code du profil déclaré.', expected_result: 'Le brut lu vaut 32767 avec une qualité hors plage.', actions: [{ action: 'force', target: 'lt101_raw', value: 24, unit: 'mA', diagnostic: true }], checks: [{ target: 'lt101_raw', operator: 'eq', value: 32767, tolerance: 0 }] }] });
  expect((await mutation(request, '/project/import', project)).ok()).toBeTruthy();
  await boot(page);
  await page.getByLabel('Scénario', { exact: true }).selectOption('browser-diagnostic');
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await page.getByRole('button', { name: 'Exécuter STEP 1', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).tags.lt101_raw.quality).toBe('out_of_range');
  await expect(page.getByRole('button', { name: 'Conforme', exact: true })).toBeEnabled();
  await page.getByLabel('Observation du testeur').fill('Code haut du profil observé, diagnostic attendu.');
  const observationSaved = page.waitForResponse(response => response.url().endsWith('/api/run/steps/diagnostic-1/observe') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Conforme', exact: true }).click();
  expect((await observationSaved).ok()).toBeTruthy();
  const final = await snapshot(request);
  expect(final.guided_steps?.[0].checks[0].passed).toBe(true);
  expect(final.guided_steps?.[0].verdict).toBe('pass');
  expect(final.result.verdict).toBe('not_evaluated');
});

test('un STEP en attente suspend les I/O et défauts, avec arrêt et rapports accessibles', async ({ page, request }) => {
  await boot(page);
  await page.getByLabel('Scénario', { exact: true }).selectOption('demo-guided-io');
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  expect((await mutation(request, '/force', { tag_id: 'lt201_raw', value: 100 })).ok()).toBeTruthy();
  expect((await mutation(request, '/force', { tag_id: 'p101_request', value: false })).ok()).toBeTruthy();
  expect((await mutation(request, '/fault', { equipment_id: 'P101', kind: 'motor_trip' })).ok()).toBeTruthy();
  await page.locator('.react-flow__node[data-id="P101"]').click();
  await expect(page.getByRole('button', { name: 'Lever', exact: true })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Libérer LT201_Raw', exact: true })).toBeEnabled();

  let holdQueued = true;
  let resolveQueued!: (state: Snapshot) => void;
  const queuedSnapshot = new Promise<Snapshot>(resolve => { resolveQueued = resolve; });
  await page.route('**/api/run/steps/*/execute', async route => {
    const response = await route.fetch();
    const queued: Snapshot = await response.json();
    resolveQueued(queued);
    await route.fulfill({ response, json: queued });
  });
  // Retain the real queued response in read-only polling until the test releases it.
  await page.route('**/api/state', async route => {
    if (holdQueued) await route.fulfill({ json: await queuedSnapshot });
    else await route.continue();
  });
  try {
    await page.getByRole('button', { name: 'Exécuter STEP 1', exact: true }).click();
    expect((await queuedSnapshot).guided_steps?.at(-1)?.state).toBe('queued');
    await expect(page.locator('.editing-locked')).toContainText('attente du cycle d’échange');
    for (const control of await page.locator('.digital-controls button:not(.io-help-hit), .analog-controls button:not(.io-help-hit), .analog-controls input, .analog-controls select').all()) await expect(control).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Injecter', exact: true })).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Lever', exact: true })).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Arrêter l’essai', exact: true })).toBeEnabled();
    await page.getByRole('button', { name: 'Tendances & rapport', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Rapport FAT', exact: true })).toBeEnabled();
    await expect(page.getByRole('button', { name: 'Données CSV', exact: true })).toBeEnabled();
    await page.getByRole('button', { name: 'P&ID', exact: true }).click();
  } finally {
    holdQueued = false;
    resolveQueued(await snapshot(request));
    await page.unrouteAll({ behavior: 'wait' });
  }
  await expect(page.locator('.digital-control[data-tag="p101_request"] .digital-push')).toBeEnabled();
  await expect(page.getByLabel('Forçage LT101_Raw')).toBeEnabled();
  await expect(page.locator('.editing-locked')).toContainText('I/O de test actives');
  expect((await snapshot(request)).result.verdict).toBe('not_evaluated');
});

test('préparer une FAT, réordonner et supprimer, puis exécuter chaque STEP avec observation humaine', async ({ page, request }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await boot(page);
  await page.getByRole('button', { name: 'Scénarios', exact: true }).click();
  await page.getByRole('button', { name: 'Nouveau scénario', exact: true }).click();
  await expect(page.getByLabel('Mode d’exécution')).toHaveValue('guided');
  await page.getByLabel('Nom du scénario').fill('FAT guidée navigateur');
  await page.getByLabel('Nom de l’étape').fill('Signal de niveau à 12 mA');
  await page.getByLabel('Instructions du testeur').fill('Comparer la conversion et le repos de la pompe.');
  await page.getByLabel('Résultat attendu', { exact: true }).fill('Le niveau lu vaut 50 % et la pompe reste arrêtée.');
  await page.getByRole('button', { name: 'Ajouter une écriture', exact: true }).click();
  await page.getByRole('button', { name: 'Ajouter une écriture', exact: true }).click();
  await page.getByLabel('Entrée écriture 1').selectOption('stop_healthy');
  await page.getByLabel('Valeur écriture 1').selectOption('true');
  await page.getByLabel('Entrée écriture 2').selectOption('lt101_raw');
  await page.getByLabel('Unité écriture 2').selectOption('mA');
  await page.getByLabel('Valeur écriture 2').fill('12');
  await expect(page.locator('[data-action="1"] .prepared-preview')).toContainText('13');
  await page.getByRole('button', { name: 'Ajouter un contrôle', exact: true }).click();
  await page.getByLabel('Variable contrôle 1').selectOption('lt101_percent');
  await page.getByLabel('Attendu contrôle 1').fill('50');
  await page.getByLabel('Tolérance contrôle 1').fill('.1');
  await page.getByRole('button', { name: 'Ajouter une étape', exact: true }).click();
  await page.getByLabel('Nom de l’étape').fill('Libérer le transmetteur');
  await page.getByLabel('Résultat attendu', { exact: true }).fill('Le niveau simulé revient à 60 %.');
  await page.getByRole('button', { name: 'Ajouter une écriture', exact: true }).click();
  await page.getByLabel('Entrée écriture 1').selectOption('lt101_raw');
  await page.getByLabel('Action écriture 1').selectOption('release');
  await page.getByRole('button', { name: 'Ajouter un contrôle', exact: true }).click();
  await page.getByLabel('Variable contrôle 1').selectOption('lt101_percent');
  await page.getByLabel('Attendu contrôle 1').fill('60');
  await page.getByRole('button', { name: 'Monter l’étape', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Préparer STEP 1 : Libérer le transmetteur', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Descendre l’étape', exact: true }).click();
  await page.getByRole('button', { name: 'Ajouter une étape', exact: true }).click();
  await page.getByRole('button', { name: 'Supprimer l’étape', exact: true }).click();
  await expect(page.locator('.guided-builder .grafcet-strip > li')).toHaveCount(2);
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Projet enregistré');
  const stored: Project = await (await request.get('/api/project')).json();
  const scenario = stored.scenarios.find(scenario => scenario.name === 'FAT guidée navigateur')!;
  expect(scenario.fat_steps).toHaveLength(2);
  expect(scenario.fat_steps![0].actions).toHaveLength(2);
  expect(scenario.fat_steps![0].actions[0].value).toBe(true);
  expect(scenario.fat_steps![0].actions[1].value).toBe(12);
  await page.locator('.guided-builder').screenshot({ path: testInfo.outputPath('guided-builder.png'), style: '.statusbar,.toast { visibility: hidden !important; }' });
  await page.getByRole('button', { name: 'P&ID', exact: true }).click();
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await page.getByRole('button', { name: 'Voir STEP 2 : Libérer le transmetteur', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Exécuter STEP 2', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Voir STEP 1 : Signal de niveau à 12 mA', exact: true }).click();
  await page.getByRole('button', { name: 'Exécuter STEP 1', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).guided_steps?.[0].state).toBe('applied');
  await expect.poll(async () => (await snapshot(request)).tags.lt101_percent.value).toBe(50);
  await page.getByLabel('Observation du testeur').fill('50 % acquis, pompe au repos.');
  await page.getByRole('button', { name: 'Voir STEP 2 : Libérer le transmetteur', exact: true }).click();
  await page.getByRole('button', { name: 'Voir STEP 1 : Signal de niveau à 12 mA', exact: true }).click();
  await expect(page.getByLabel('Observation du testeur')).toHaveValue('50 % acquis, pompe au repos.');
  await page.getByRole('button', { name: 'Tendances & rapport', exact: true }).click();
  await page.getByRole('button', { name: 'P&ID', exact: true }).click();
  await expect(page.getByLabel('Observation du testeur')).toHaveValue('50 % acquis, pompe au repos.');
  await expect(page.getByRole('button', { name: 'Conforme', exact: true })).toBeEnabled();
  await page.locator('.guided-run').screenshot({ path: testInfo.outputPath('guided-run-applied.png'), style: '.statusbar,.toast { visibility: hidden !important; }' });
  await page.getByRole('button', { name: 'Conforme', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Exécuter STEP 2', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Exécuter STEP 2', exact: true }).click();
  await expect.poll(async () => (await snapshot(request)).guided_steps?.[1].state).toBe('applied');
  await expect.poll(async () => Number((await snapshot(request)).tags.lt101_percent.value)).toBeCloseTo(60, 2);
  await page.getByLabel('Observation du testeur').fill('Retour à la mesure simulée constaté.');
  await page.getByRole('button', { name: 'Conforme', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En pause');
  await expect(page.locator('.fat-human-result')).toContainText('Conclusion FAT humaine : à renseigner');
  const final = await snapshot(request);
  expect(final.guided_steps?.map(step => step.state)).toEqual(['reviewed', 'reviewed']);
  expect(final.guided_steps?.map(step => step.verdict)).toEqual(['pass', 'pass']);
  expect(final.guided_steps?.[0].observation).toBe('50 % acquis, pompe au repos.');
  expect(final.result.verdict).toBe('not_evaluated');
  expect(final.events.filter(event => event.kind === 'fat_step_observed')).toHaveLength(2);
  expect(errors).toEqual([]);
});
