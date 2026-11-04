import { defineConfig } from '@playwright/test';
import { fileURLToPath } from 'node:url';

// Explicit local visual check, outside npm test: a real maximized Windows window.
export default defineConfig({
  testDir: '.', testMatch: 'capture-native.ts', workers: 1, retries: 0, timeout: 30_000,
  reporter: [['list'], ['json', { outputFile: fileURLToPath(new URL('../test-results/native-results.json', import.meta.url)) }]],
  outputDir: '../test-results/native-artifacts',
  use: { baseURL: 'http://127.0.0.1:8766', browserName: 'chromium', channel: 'msedge', headless: false, viewport: null, locale: 'fr-CH', launchOptions: { args: ['--start-maximized'] }, actionTimeout: 6_000, screenshot: 'only-on-failure' },
  webServer: { command: 'node tests/serve.mjs', cwd: fileURLToPath(new URL('..', import.meta.url)), url: 'http://127.0.0.1:8766/api/health', reuseExistingServer: false, timeout: 30_000 },
});
