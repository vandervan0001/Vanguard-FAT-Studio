import { defineConfig } from '../../../../../frontend/node_modules/@playwright/test/index.js';
import { resolve } from 'node:path';
const frontend = resolve(__dirname, '../../../../../frontend');
export default defineConfig({
  testDir: '.', testMatch: 'framing-check.spec.ts', workers: 1, retries: 0, timeout: 30_000,
  outputDir: resolve(frontend, 'test-results/framing-artifacts'),
  reporter: [['list'], ['json', { outputFile: resolve(__dirname, 'framing-results.json') }]],
  use: { baseURL: 'http://127.0.0.1:8766', browserName: 'chromium', channel: 'msedge', headless: false, viewport: null, locale: 'fr-CH', launchOptions: { args: ['--start-maximized'] } },
  webServer: { command: 'node tests/serve.mjs', cwd: frontend, url: 'http://127.0.0.1:8766/api/health', reuseExistingServer: false, timeout: 30_000 },
});
