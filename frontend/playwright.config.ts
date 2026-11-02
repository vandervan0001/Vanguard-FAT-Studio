import { defineConfig } from '@playwright/test';

const externalServer = process.env.FAT_E2E_BASE_URL;
const baseURL = externalServer ?? 'http://127.0.0.1:8766';
const windowsCI = process.platform === 'win32' && Boolean(process.env.CI);
if (!['127.0.0.1', 'localhost', '[::1]'].includes(new URL(baseURL).hostname)) {
  throw new Error('Les tests FAT modifient leurs données : seule une URL de test locale est autorisée.');
}

export default defineConfig({
  testDir: './tests',
  // Windows CI delivered node selection after the original 6 s input budget.
  timeout: windowsCI ? 60_000 : 30_000,
  expect: { timeout: 6_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'test-results/results.json' }]],
  outputDir: 'test-results/artifacts',
  use: {
    baseURL,
    browserName: 'chromium',
    viewport: { width: 1440, height: 1000 },
    locale: 'fr-CH',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    actionTimeout: windowsCI ? 12_000 : 6_000,
  },
  webServer: externalServer ? undefined : {
    command: 'node tests/serve.mjs',
    url: `${baseURL}/api/health`,
    reuseExistingServer: false,
    timeout: 30_000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
