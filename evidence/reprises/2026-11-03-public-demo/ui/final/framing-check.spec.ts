import { expect, test } from '../../../../../frontend/node_modules/@playwright/test/index.js';
import { writeFile } from 'node:fs/promises';

test('un cran de zoom dégage les instruments et la minimap sans modifier le projet', async ({ page, request }, testInfo) => {
  const { token } = await (await request.get('/api/session')).json();
  expect((await request.post('/api/pilot/load', { headers: { 'X-FAT-Token': token }, data: {} })).ok()).toBeTruthy();
  await page.goto('/');
  await page.getByLabel('Scénario', { exact: true }).selectOption('demo-guided-io');
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.locator('.status-badge')).toHaveText('En cours');
  await page.getByRole('button', { name: 'Mode présentation', exact: true }).click();
  await page.waitForTimeout(500);
  await page.getByRole('button', { name: 'Vue complète', exact: true }).click();
  await page.waitForTimeout(350);
  const project = await (await request.get('/api/project')).json();
  const inspect = () => page.evaluate(() => {
    const box = (selector: string) => { const r = document.querySelector(selector)!.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }; };
    const overlap = (a: ReturnType<typeof box>, b: ReturnType<typeof box>) => a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
    const lt101 = box('[data-id="LT101"] .node-label'), valve = box('[data-id="XV301"] .process-symbol');
    const banner = box('.editing-locked'), topline = box('.canvas-topline'), minimap = box('.react-flow__minimap');
    return { lt101, valve, banner, topline, minimap, lt101_hidden: overlap(lt101, banner) || overlap(lt101, topline), valve_hidden: overlap(valve, minimap) };
  });
  const before = await inspect();
  await page.getByRole('button', { name: 'Zoom arrière', exact: true }).click();
  await page.waitForTimeout(350);
  const after = await inspect();
  await page.screenshot({ path: testInfo.outputPath('presentation-one-zoom-out.png') });
  await writeFile(testInfo.outputPath('framing-geometry.json'), JSON.stringify({ viewport: null, mode: 'temporary demonstration on 8766 only', before, after, zoom_out_clicks: 1 }, null, 2));
  expect(after.lt101_hidden).toBe(false);
  expect(after.valve_hidden).toBe(false);
  expect(await (await request.get('/api/project')).json()).toEqual(project);
  expect((await (await request.get('/api/state')).json()).guided_steps).toEqual([]);
  await page.getByRole('button', { name: 'Arrêter l’essai', exact: true }).click();
});
