import { expect, test } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
import type { Project } from '../src/types';

test('laboratoire dans une fenêtre native maximisée sans viewport ni écran émulés', async ({ page, request }, testInfo) => {
  const { token } = await (await request.get('/api/session')).json();
  const change = (path: string, body: unknown = {}) => request.post(`/api${path}`, { headers: { 'X-FAT-Token': token }, data: body });
  expect((await change('/pilot/load')).ok()).toBeTruthy();
  const project: Project = await (await request.get('/api/project')).json();
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByLabel('Nom du projet')).toHaveValue(project.name);
  expect(page.viewportSize()).toBeNull();
  const cdp = await page.context().newCDPSession(page);
  const window = await cdp.send('Browser.getWindowForTarget');
  if (window.bounds.windowState !== 'maximized') await cdp.send('Browser.setWindowBounds', { windowId: window.windowId, bounds: { windowState: 'maximized' } });
  await expect.poll(async () => (await cdp.send('Browser.getWindowBounds', { windowId: window.windowId })).bounds.windowState).toBe('maximized');
  await page.waitForTimeout(300); // Let Windows finish the real maximize transition before measuring CSS pixels.
  const geometry = await page.evaluate(() => ({ width: innerWidth, height: innerHeight, screenWidth: screen.width, screenHeight: screen.height, devicePixelRatio, documentWidth: document.documentElement.scrollWidth }));
  expect(geometry.width).toBeGreaterThanOrEqual(1280);
  expect(geometry.documentWidth).toBeLessThanOrEqual(geometry.width);
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  for (const tag_id of ['p101_request', 'xv101_request', 'p201_request', 'xv201_request', 'p202_request', 'xv202_request']) { const response = await change('/force', { tag_id, value: true }); expect(response.ok(), await response.text()).toBeTruthy(); }
  await expect(page.locator('.react-flow__node[data-id="P101"] .equipment-node')).toHaveAttribute('data-animation-active', 'true');
  const toast = page.getByRole('button', { name: 'Fermer la notification', exact: true });
  if (await toast.isVisible()) await toast.click();
  await page.screenshot({ path: testInfo.outputPath('public-native-console.png') });
  await page.getByRole('button', { name: 'Mode présentation', exact: true }).click();
  await expect(page.getByLabel('Entrées digitales', { exact: true })).toBeHidden();
  await page.waitForTimeout(500); // FitView runs after the layout resize, then animates for 150 ms.
  await page.screenshot({ path: testInfo.outputPath('public-native-presentation.png') });
  const bounds = (await cdp.send('Browser.getWindowBounds', { windowId: window.windowId })).bounds;
  const browser = await cdp.send('Browser.getVersion');
  await writeFile(testInfo.outputPath('native-window.json'), JSON.stringify({ viewport: null, windowBounds: bounds, browser_version: browser.product, ...geometry, browser_errors: errors, mode: 'temporary demo fixture on port 8766; no PLC' }, null, 2));
  expect(errors).toEqual([]);
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
});
