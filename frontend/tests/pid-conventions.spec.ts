import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import type { PidConventions, Project } from '../src/types';

async function headers(request: APIRequestContext) {
  const [session, project, state] = await Promise.all([request.get('/api/session'), request.get('/api/project'), request.get('/api/state')]);
  return { 'X-FAT-Token': (await session.json()).token, 'X-FAT-Project-ID': (await project.json()).id, 'X-FAT-Project-Revision': project.headers()['x-fat-project-revision'], 'X-FAT-Run-ID': (await state.json()).run_id ?? '' };
}
async function drawing(page: Page) {
  await page.getByRole('button', { name: 'Échanges P&ID', exact: true }).click();
  await page.getByRole('button', { name: 'Mise en page', exact: true }).click();
  await page.getByText('Format et folio', { exact: true }).click();
}
async function closeExchange(page: Page) {
  await page.getByRole('button', { name: 'Fermer les échanges P&ID', exact: true }).click();
}
async function saveLayout(page: Page) {
  const saved = page.waitForResponse(response => new URL(response.url()).pathname === '/api/project' && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Enregistrer la mise en page', exact: true }).click();
  expect((await saved).ok()).toBe(true);
  await expect(page.locator('.pid-progress')).toContainText('Mise en page et brouillon du projet enregistrés');
}

test.beforeEach(async ({ request, page }) => {
  expect((await request.get('/api/health')).ok()).toBe(true);
  if (['running', 'paused', 'error'].includes((await (await request.get('/api/state')).json()).status)) expect((await request.post('/api/run/stop', { headers: await headers(request), data: {} })).ok()).toBe(true);
  expect((await request.post('/api/demo/load', { headers: await headers(request), data: {} })).ok()).toBe(true);
  const base: Project = await (await request.get('/api/project')).json();
  const project: Project = { ...base, name: 'Conventions locales', tags: [], scenarios: [], pid_document: null, equipment: [
    { id: 'P1', type: 'pid_symbol', symbol_kind: 'pump_general', name: 'REPERE-SOURCE-1', description: '', unit: '', position: { x: 100, y: 100 }, params: {}, bindings: {} },
    { id: 'P2', type: 'pid_symbol', symbol_kind: 'pump_general', name: 'REPERE-SOURCE-2', description: '', unit: '', position: { x: 550, y: 100 }, params: {}, bindings: {} },
  ], connections: [{ id: 'service_line', source: 'P1', target: 'P2', label: 'Texte source conservé', directed: true, service: 'unspecified' }] };
  expect((await request.put('/api/project', { headers: await headers(request), data: project })).ok()).toBe(true);
  await page.goto('/');
  await expect(page.getByLabel('Nom du projet')).toHaveValue('Conventions locales');
  await page.getByRole('button', { name: 'Construire', exact: true }).click();
});

test('service explicite, code et couleur persistent avec les deux présentations et le noir et blanc', async ({ page, request }, testInfo) => {
  const conventions: PidConventions = await (await request.get('/api/pid/conventions')).json();
  const hot = conventions.services.find(service => service.id === 'hot_supply')!;
  const edge = page.locator('.react-flow__edge[data-id="service_line"]');
  await edge.locator('.react-flow__edge-textbg').click();
  await expect(page.getByLabel('Service de la liaison')).toHaveValue('unspecified');
  await expect(page.getByLabel('Service de la liaison').locator('option')).toHaveCount(10);
  await page.getByLabel('Service de la liaison').selectOption('hot_supply');
  await expect(page.locator('.pipe-core[data-edge-id="service_line"]')).toHaveAttribute('data-service', 'hot_supply');
  await expect(edge.locator('.react-flow__edge-text')).toHaveText(`[${hot.code}] · Texte source conservé`);
  const hotRGB = `rgb(${parseInt(hot.color.slice(1, 3), 16)}, ${parseInt(hot.color.slice(3, 5), 16)}, ${parseInt(hot.color.slice(5, 7), 16)})`;
  await expect(edge.locator('.react-flow__edge-path')).toHaveCSS('stroke', hotRGB);
  await expect(page.getByLabel('Légende du P&ID')).toContainText(hot.label);
  await expect(page.getByLabel('Légende du P&ID')).toContainText(hot.code);
  await page.screenshot({ path: testInfo.outputPath('service-selected-colour-desktop.png') });
  expect((await (await request.get('/api/project')).json()).connections[0].service).toBe('unspecified');
  await drawing(page);
  await expect(page.getByLabel('Présentation du cartouche')).toHaveValue('compact');
  await expect(page.getByLabel('Couleurs du dessin')).toHaveValue('service');
  await page.getByLabel('Présentation du cartouche').selectOption('full');
  await page.getByLabel('Couleurs du dessin').selectOption('monochrome');
  await saveLayout(page);
  await closeExchange(page);
  await expect(edge.locator('.react-flow__edge-path')).toHaveCSS('stroke', 'rgb(0, 0, 0)');
  await expect(edge.locator('.react-flow__edge-text')).toContainText(hot.code);
  const stored: Project = await (await request.get('/api/project')).json();
  expect(stored.pid_drawing).toMatchObject({ layout_style: 'full', color_mode: 'monochrome' });
  expect(stored.connections[0]).toMatchObject({ service: 'hot_supply', label: 'Texte source conservé' });
  expect(stored.equipment.map(item => item.name)).toEqual(['REPERE-SOURCE-1', 'REPERE-SOURCE-2']);
  await drawing(page);
  await page.getByLabel('Présentation du cartouche').selectOption('compact');
  await page.getByLabel('Couleurs du dessin').selectOption('service');
  await saveLayout(page);
  await closeExchange(page);
  await page.reload();
  await expect(edge.locator('.react-flow__edge-path')).toHaveCSS('stroke', hotRGB);
  await expect(edge.locator('.react-flow__edge-text')).toContainText('Texte source conservé');
  await page.screenshot({ path: testInfo.outputPath('service-colour-canvas.png') });
  await page.getByRole('button', { name: 'Construire', exact: true }).click();
  await edge.locator('.react-flow__edge-textbg').click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByLabel('Service de la liaison')).toHaveValue('hot_supply');
  await page.screenshot({ path: testInfo.outputPath('service-colour-mobile.png'), fullPage: true });
  expect(await page.locator('.workbench').evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
});

test('bibliothèque sourcée, repères fonctionnels, références et polices CAO sont consultables sans renommer la source', async ({ page, request }, testInfo) => {
  await page.getByLabel('Rechercher dans la bibliothèque').fill('transmetteur de débit');
  await page.getByRole('button', { name: 'Ajouter Transmetteur de débit (FT)', exact: true }).click();
  await expect(page.getByLabel('Nom / repère')).toHaveValue('FT-101');
  await expect(page.locator('.react-flow__node [data-instrument-code="FT"]')).toHaveText('FT');
  await page.getByLabel('Rotation du symbole').selectOption('90');
  await expect(page.locator('.react-flow__node [data-instrument-code="FT"]')).not.toHaveAttribute('transform');
  await page.getByLabel('Rechercher dans la bibliothèque').fill('pompe, représentation générale');
  await page.getByRole('button', { name: 'Ajouter Pompe, représentation générale', exact: true }).click();
  await expect(page.locator('.pid-symbol-source')).toContainText('pyflowsheet');
  await expect(page.locator('.pid-symbol-source')).toContainText('MIT');
  await page.getByRole('button', { name: 'Échanges P&ID', exact: true }).click();
  await page.getByRole('button', { name: 'Catalogue public', exact: true }).click();
  const guide = page.getByRole('region', { name: 'Conventions et références P&ID' });
  await expect(guide).toContainText('sans renommer les repères importés');
  await guide.getByText('Repères usuels d’instrumentation', { exact: true }).click();
  await expect(guide.getByRole('cell', { name: 'FT-101', exact: true })).toBeVisible();
  await guide.getByText('Sources et portée des références', { exact: true }).click();
  await expect(guide.getByRole('link', { name: 'ANSI/ISA-5.1-2024', exact: true })).toHaveAttribute('href', /https:\/\/www\.isa\.org\//);
  await expect(guide.getByRole('link', { name: 'ISO 10628-2:2012', exact: true })).toHaveAttribute('href', /https:\/\/www\.iso\.org\//);
  await guide.getByText('Services, codes et couleurs du projet', { exact: true }).click();
  await expect(guide.locator('.pid-service-list li')).toHaveCount(10);
  await page.screenshot({ path: testInfo.outputPath('conventions-guide-desktop.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: testInfo.outputPath('conventions-guide-mobile.png') });
  expect(await page.locator('.pid-exchange').evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('button', { name: 'Exporter le P&ID', exact: true }).click();
  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Télécharger les polices CAO et leur licence', exact: true }).click();
  const downloaded = await download;
  expect(downloaded.suggestedFilename()).toMatch(/\.zip$/);
  expect((await readFile((await downloaded.path())!)).subarray(0, 2).toString()).toBe('PK');
  expect((await (await request.get('/api/project')).json()).equipment.map((item: { name: string }) => item.name)).toEqual(['REPERE-SOURCE-1', 'REPERE-SOURCE-2']);
});
