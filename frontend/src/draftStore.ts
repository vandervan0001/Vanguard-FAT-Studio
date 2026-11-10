import type { Project, ReportDraft, ScenarioDraft } from './types';

const PREFIX = 'vanguard:draft:1:';
export type LocalDraft = {
  version: 1; scope: string; revision: string; updatedAt: string; project: Project;
  projectDirty: boolean; scenario: ScenarioDraft | null; report: ReportDraft;
  observations: Record<string, string>; tab: string;
};

export function draftTab(): string {
  // sessionStorage is cloned by Duplicate tab. Each document needs its own writer.
  // Reload discovers the previous document's saved draft by scope and project.
  return crypto.randomUUID();
}

function prefix(scope: string, projectId: string) { return `${PREFIX}${encodeURIComponent(scope)}:${encodeURIComponent(projectId)}:`; }
export function draftKey(draft: Pick<LocalDraft, 'scope' | 'project' | 'tab'>) { return prefix(draft.scope, draft.project.id) + draft.tab; }
export function writeDraft(draft: LocalDraft) {
  const text = JSON.stringify(draft);
  if (text.length > 5 * 1024 * 1024) throw new Error('Brouillon trop volumineux pour la récupération locale. Téléchargez-le ou enregistrez le projet.');
  localStorage.setItem(draftKey(draft), text);
}
export function removeDraft(scope: string, projectId: string, tab: string) { localStorage.removeItem(prefix(scope, projectId) + tab); }
export function acknowledgeDraft(draft: LocalDraft) {
  // Hide exactly this snapshot without deleting another open document's backup.
  localStorage.setItem(`${PREFIX}ack:${draftKey(draft)}`, draft.updatedAt);
}

/** Storage is untrusted. The server validates the full project again before restoring it. */
export function readDraft(scope: string, projectId: string, tab: string): LocalDraft | null {
  const candidates: LocalDraft[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (!key?.startsWith(prefix(scope, projectId))) continue;
    try {
      const text = localStorage.getItem(key);
      if (!text || text.length > 5 * 1024 * 1024) continue;
      const value = JSON.parse(text) as LocalDraft;
      if (value.version !== 1 || value.scope !== scope || value.project?.id !== projectId || typeof value.tab !== 'string' || typeof value.revision !== 'string' || !Number.isFinite(Date.parse(value.updatedAt))) continue;
      if (typeof value.projectDirty !== 'boolean' || !value.report || !['pass', 'fail', 'not_evaluated'].includes(value.report.verdict) || typeof value.report.comment !== 'string' || typeof value.report.marker !== 'string' || typeof value.report.resultDirty !== 'boolean') continue;
      if (value.report.runId !== null && typeof value.report.runId !== 'string') continue;
      if (value.scenario !== null && (typeof value.scenario?.scenarioId !== 'string' || typeof value.scenario.text !== 'string')) continue;
      if (!value.observations || typeof value.observations !== 'object' || Array.isArray(value.observations) || Object.values(value.observations).some(item => typeof item !== 'string')) continue;
      if (localStorage.getItem(`${PREFIX}ack:${key}`) === value.updatedAt) continue;
      candidates.push(value);
    } catch { /* An unreadable entry is retained for inspection, never applied. */ }
  }
  return candidates.sort((a, b) => Number(b.tab === tab) - Number(a.tab === tab) || Date.parse(b.updatedAt) - Date.parse(a.updatedAt))[0] ?? null;
}
