let csrfToken = '';
let currentProjectId = '';
let currentProjectRevision = '';
let currentRunId = '';
let mutationVersion = 0;
let mutations: Promise<unknown> = Promise.resolve();

export function setProjectContext(projectId: string) {
  if (projectId !== currentProjectId) { currentProjectRevision = ''; currentRunId = ''; }
  currentProjectId = projectId;
}
export function getProjectContext() { return currentProjectId; }
export function getProjectRevision() { return currentProjectRevision; }
export function setRunContext(runId: string | null) { currentRunId = runId ?? ''; }
export function getMutationVersion() { return mutationVersion; }

export async function initSession(signal?: AbortSignal): Promise<void> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal?.addEventListener('abort', cancel, { once: true });
  if (signal?.aborted) controller.abort();
  const timeout = setTimeout(cancel, 5000);
  try {
    const response = await fetch('/api/session', { cache: 'no-store', signal: controller.signal });
    if (!response.ok) throw new Error('Le service local ne répond pas. Vérifiez que FAT Studio est démarré.');
    const data: unknown = await response.json();
    if (!data || typeof data !== 'object' || !('token' in data) || typeof data.token !== 'string' || !data.token) throw new Error('Le service local n’a pas fourni de session valide. Rechargez la page.');
    csrfToken = data.token;
  } catch (error) {
    if (controller.signal.aborted) throw new Error('Le service local ne répond pas. Vérifiez que FAT Studio est démarré, puis réessayez.');
    throw error;
  } finally { clearTimeout(timeout); signal?.removeEventListener('abort', cancel); }
}

function readable(detail: unknown): string {
  if (detail === null || detail === undefined) return 'Erreur du service local.';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(item => typeof item === 'object' && item && 'msg' in item ? `${'loc' in item && Array.isArray(item.loc) ? item.loc.join('.') + ' : ' : ''}${item.msg}` : readable(item)).join('\n');
  if (detail && typeof detail === 'object' && 'message' in detail) return String(detail.message);
  return JSON.stringify(detail, null, 2) ?? 'Erreur du service local.';
}

type RequestContext = { projectId: string; revision: string; runId: string };

export function api<T>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal, expectedRunId?: string | null): Promise<T> {
  // Retain the target of the user's action while queued or refreshing an expired session.
  const context = { projectId: currentProjectId, revision: currentProjectRevision, runId: expectedRunId === undefined ? currentRunId : expectedRunId ?? '' };
  const request = () => requestApi<T>(path, method, body, signal, context);
  if (method === 'GET') return request();
  mutationVersion++;
  const result = mutations.then(request, request).finally(() => { mutationVersion++; });
  mutations = result.catch(() => undefined);
  return result;
}

async function requestApi<T>(path: string, method: string, body: unknown, signal: AbortSignal | undefined, context: RequestContext, refreshed = false): Promise<T> {
  const projectSensitive = /^\/(run|force|fault|markers|result)(\/|$)/.test(path) || (path === '/project' && method === 'PUT') || (path === '/mapping' && method === 'POST');
  const runSensitive = /^\/(run|force|fault|markers|result)(\/|$)/.test(path);
  const response = await fetch(`/api${path}`, {
    method, cache: 'no-store', signal,
    headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(method !== 'GET' ? { 'X-FAT-Token': csrfToken, ...(projectSensitive && context.projectId ? { 'X-FAT-Project-ID': context.projectId, ...(context.revision ? { 'X-FAT-Project-Revision': context.revision } : {}) } : {}), ...(runSensitive ? { 'X-FAT-Run-ID': context.runId } : {}) } : {}) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  // A rejected session has no side effect. Refresh once after a local server restart.
  if (response.status === 403 && method !== 'GET' && !refreshed) {
    await initSession();
    return requestApi<T>(path, method, body, signal, context, true);
  }
  if (!response.ok) {
    const error: unknown = await response.json().catch(() => ({ detail: `Erreur HTTP ${response.status} du service local.` }));
    throw new Error(readable(error && typeof error === 'object' && 'detail' in error ? error.detail : error) || `Erreur HTTP ${response.status}.`);
  }
  try {
    const data: unknown = await response.json();
    const projectResponse = path === '/project' || (method === 'POST' && (path === '/project/import' || path === '/projects' || path === '/demo/load' || path === '/mapping' || /^\/projects\/[^/]+\/load$/.test(path)));
    if (projectResponse && data && typeof data === 'object' && 'id' in data && typeof data.id === 'string' && 'equipment' in data && Array.isArray(data.equipment)) {
      // Never accept a newer baseline from polling state: that would hide a conflict.
      setProjectContext(data.id);
      currentProjectRevision = response.headers.get('X-FAT-Project-Revision') ?? '';
      if (method !== 'GET') currentRunId = '';
    }
    return data as T;
  }
  catch { throw new Error(`Réponse inattendue du service local (HTTP ${response.status}, JSON attendu).`); }
}

export function downloadText(text: string, name: string, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement('a');
  link.href = url; link.download = name;
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function downloadMapping(): Promise<void> {
  const projectId = currentProjectId;
  const revision = currentProjectRevision;
  const response = await fetch('/api/mapping', {
    cache: 'no-store',
    headers: { 'X-FAT-Project-ID': projectId, 'X-FAT-Project-Revision': revision },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: `Erreur HTTP ${response.status} du service local.` }));
    throw new Error(readable(error?.detail ?? error));
  }
  if (revision && response.headers.get('X-FAT-Project-Revision') !== revision) throw new Error('Le projet actif a changé ; recharger avant d’exporter le mapping.');
  downloadText(await response.text(), 'fat-mapping.csv', 'text/csv;charset=utf-8');
}

export function download(path: string) {
  const link = document.createElement('a');
  link.href = `/api${path}`;
  link.download = '';
  document.body.append(link);
  link.click();
  link.remove();
}
