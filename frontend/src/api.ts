let csrfToken = '';
let currentProjectId = '';
let currentProjectRevision = '';

export function setProjectContext(projectId: string) { currentProjectId = projectId; }
export function getProjectRevision() { return currentProjectRevision; }

export async function initSession(): Promise<void> {
  const response = await fetch('/api/session', { cache: 'no-store' });
  if (!response.ok) throw new Error('Le service local ne répond pas. Vérifiez que FAT Studio est démarré.');
  const data: unknown = await response.json();
  if (!data || typeof data !== 'object' || !('token' in data) || typeof data.token !== 'string' || !data.token) throw new Error('Le service local n’a pas fourni de session valide. Rechargez la page.');
  csrfToken = data.token;
}

function readable(detail: unknown): string {
  if (detail === null || detail === undefined) return 'Erreur du service local.';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(item => typeof item === 'object' && item && 'msg' in item ? `${'loc' in item && Array.isArray(item.loc) ? item.loc.join('.') + ' : ' : ''}${item.msg}` : readable(item)).join('\n');
  if (detail && typeof detail === 'object' && 'message' in detail) return String(detail.message);
  return JSON.stringify(detail, null, 2) ?? 'Erreur du service local.';
}

export async function api<T>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal, refreshed = false): Promise<T> {
  const projectSensitive = /^\/(run|force|fault|markers|result)(\/|$)/.test(path) || (path === '/project' && method === 'PUT') || (path === '/mapping' && method === 'POST');
  const response = await fetch(`/api${path}`, {
    method, cache: 'no-store', signal,
    headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(method !== 'GET' ? { 'X-FAT-Token': csrfToken, ...(projectSensitive && currentProjectId ? { 'X-FAT-Project-ID': currentProjectId, ...(currentProjectRevision ? { 'X-FAT-Project-Revision': currentProjectRevision } : {}) } : {}) } : {}) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  // A rejected session has no side effect. Refresh once after a local server restart.
  if (response.status === 403 && method !== 'GET' && !refreshed) {
    await initSession();
    return api<T>(path, method, body, signal, true);
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
      currentProjectRevision = response.headers.get('X-FAT-Project-Revision') ?? '';
    }
    return data as T;
  }
  catch { throw new Error(`Réponse inattendue du service local (HTTP ${response.status}, JSON attendu).`); }
}

export function download(path: string) {
  const link = document.createElement('a');
  link.href = `/api${path}`;
  link.download = '';
  document.body.append(link);
  link.click();
  link.remove();
}
