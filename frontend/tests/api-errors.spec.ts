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
    if (String(input) === '/api/project') return new Response('{"id":"premier-projet","equipment":[]}', { status: 200, headers: { 'X-FAT-Project-Revision': 'premiere-revision' } });
    if (String(input) === '/api/session') {
      setProjectContext('autre-projet');
      setRunContext('autre-essai');
      return new Response('{"token":"session-renouvelee"}', { status: 200 });
    }
    headers.push(init?.headers as Record<string, string>);
    return ++attempts === 1 ? new Response('{"detail":"Session expirée"}', { status: 403 }) : new Response('{"detail":"Contexte périmé"}', { status: 409 });
  };
  await api('/project');
  await expect(api('/pilot/load', 'POST', {})).rejects.toThrow('Contexte périmé');
  expect(headers).toHaveLength(2);
  for (const header of headers) {
    expect(header['X-FAT-Project-ID']).toBe('premier-projet');
    expect(header['X-FAT-Project-Revision']).toBe('premiere-revision');
    expect(header['X-FAT-Run-ID']).toBe('premier-essai');
  }
});

test('restaurer une archive conserve les octets et le contexte capturés après renouvellement de session', async () => {
  setProjectContext('projet-archive'); setRunContext('essai-archive');
  const archive = new Blob([new Uint8Array([80, 75, 3, 4, 0, 255])], { type: 'application/zip' });
  const calls: RequestInit[] = [];
  globalThis.fetch = async (input, init) => {
    if (String(input) === '/api/project') return new Response('{"id":"projet-archive","equipment":[]}', { headers: { 'X-FAT-Project-Revision': 'revision-espace-original' } });
    if (String(input) === '/api/session') { setProjectContext('autre-espace'); setRunContext(null); return new Response('{"token":"archive-renouvelee"}'); }
    calls.push(init!);
    return calls.length === 1 ? new Response('{"detail":"Session expirée"}', { status: 403 }) : new Response('{"detail":"Contexte périmé"}', { status: 409 });
  };
  await api('/project');
  await expect(api('/project/archive/import', 'POST', archive)).rejects.toThrow('Contexte périmé');
  expect(calls).toHaveLength(2);
  for (const call of calls) {
    expect(call.body).toBe(archive);
    expect(Array.from(new Uint8Array(await (call.body as Blob).arrayBuffer()))).toEqual([80, 75, 3, 4, 0, 255]);
    expect(call.headers).toMatchObject({ 'Content-Type': 'application/zip', 'X-FAT-Project-ID': 'projet-archive', 'X-FAT-Project-Revision': 'revision-espace-original', 'X-FAT-Run-ID': 'essai-archive' });
  }
});

test('ouvrir le dossier déjà actif conserve le run annoncé par le serveur', async () => {
  setProjectContext('projet-identique'); setRunContext('essai-conserve');
  const stops: Record<string, string>[] = [];
  globalThis.fetch = async (input, init) => {
    if (String(input) === '/api/run/stop') { stops.push(init!.headers as Record<string, string>); return new Response('{}'); }
    return new Response('{"id":"projet-identique","equipment":[]}', { headers: { 'X-FAT-Project-Revision': 'revision-espace', 'X-FAT-Run-ID': 'essai-conserve' } });
  };
  await api('/project');
  await api('/workspaces/default/open', 'POST', {});
  await api('/run/stop', 'POST', {});
  expect(stops[0]).toMatchObject({ 'X-FAT-Project-ID': 'projet-identique', 'X-FAT-Project-Revision': 'revision-espace', 'X-FAT-Run-ID': 'essai-conserve' });
});
