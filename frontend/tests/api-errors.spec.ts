import { expect, test } from '@playwright/test';
import { api, setProjectContext, setRunContext } from '../src/api';

const originalFetch = globalThis.fetch;
test.afterEach(() => { globalThis.fetch = originalFetch; setProjectContext(''); });

test('une erreur non JSON ou un corps null reste une erreur lisible', async () => {
  globalThis.fetch = async () => new Response('<html>Gateway unavailable</html>', { status: 502 });
  await expect(api('/state')).rejects.toThrow('Erreur HTTP 502');
  globalThis.fetch = async () => new Response('null', { status: 400, headers: { 'Content-Type': 'application/json' } });
  await expect(api('/state')).rejects.toThrow('Erreur du service local.');
  globalThis.fetch = async () => new Response('<html>Unexpected success</html>', { status: 200 });
  await expect(api('/state')).rejects.toThrow('JSON attendu');
});

test('un jeton expiré est renouvelé une seule fois et conserve le contexte projet', async () => {
  setProjectContext('tank-demo');
  const calls: { path: string; headers: Record<string, string> }[] = [];
  globalThis.fetch = async (input, init) => {
    const path = String(input);
    calls.push({ path, headers: (init?.headers ?? {}) as Record<string, string> });
    if (path === '/api/session') return new Response('{"token":"nouveau-jeton-test"}', { status: 200 });
    return new Response('{"detail":"Session locale expirée"}', { status: 403 });
  };
  await expect(api('/run/pause', 'POST', {})).rejects.toThrow('Session locale expirée');
  expect(calls.map(call => call.path)).toEqual(['/api/run/pause', '/api/session', '/api/run/pause']);
  expect(calls[2].headers['X-FAT-Token']).toBe('nouveau-jeton-test');
  expect(calls[0].headers['X-FAT-Project-ID']).toBe('tank-demo');
  expect(calls[2].headers['X-FAT-Project-ID']).toBe('tank-demo');
});

test('un renouvellement de session ne redirige pas une action vers un autre projet ou essai', async () => {
  setProjectContext('premier-projet');
  setRunContext('premier-essai');
  const headers: Record<string, string>[] = [];
  let attempts = 0;
  globalThis.fetch = async (input, init) => {
    if (String(input) === '/api/session') {
      setProjectContext('autre-projet');
      setRunContext('autre-essai');
      return new Response('{"token":"session-renouvelee"}', { status: 200 });
    }
    headers.push(init?.headers as Record<string, string>);
    return ++attempts === 1 ? new Response('{"detail":"Session expirée"}', { status: 403 }) : new Response('{"detail":"Contexte périmé"}', { status: 409 });
  };
  await expect(api('/result', 'POST', { verdict: 'fail', comment: 'Ancien essai' })).rejects.toThrow('Contexte périmé');
  expect(headers).toHaveLength(2);
  for (const header of headers) {
    expect(header['X-FAT-Project-ID']).toBe('premier-projet');
    expect(header['X-FAT-Run-ID']).toBe('premier-essai');
  }
});
