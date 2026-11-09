import { useEffect, useState } from 'react';
import { ArrowRight, CheckCircle2, CircleAlert, LoaderCircle } from 'lucide-react';
import { api } from './api';
import type { CatalogItem, Project, Tab, Validation } from './types';

export type Correction = { tab: Tab; equipmentId?: string; tagId?: string; port?: string; field?: string; scenarioId?: string };
function entryAt<T extends { id: string }>(entries: T[], key: string | undefined) { return key === undefined ? undefined : /^\d+$/.test(key) ? entries[Number(key)] : entries.find(entry => entry.id === key); }
export function correctionFor(project: Project, path: string): Correction {
  const [section, index, kind, field] = path.split('.');
  if (section === 'equipment') return { tab: 'pid', equipmentId: entryAt(project.equipment, index)?.id, ...(kind === 'bindings' ? { port: field } : { field: field ?? kind }) };
  if (section === 'connections') return { tab: 'pid', equipmentId: project.connections[Number(index)]?.source };
  if (section === 'tags') return { tab: 'tags', tagId: entryAt(project.tags, index)?.id, field: [kind, field].filter(Boolean).join('.') };
  if (section === 'scenarios') return { tab: 'scenarios', scenarioId: project.scenarios[Number(index)]?.id };
  return { tab: 'connection', field: section === 'plc' ? index ?? 'endpoint' : section === 'simulation' ? index : 'endpoint' };
}
function titleFor(project: Project, catalog: CatalogItem[], path: string) {
  const [section, index, kind, field] = path.split('.');
  if (section === 'equipment') {
    const equipment = entryAt(project.equipment, index);
    const spec = catalog.find(item => item.type === equipment?.type);
    const label = kind === 'bindings' ? spec?.ports[field]?.label : spec?.parameters[field]?.label;
    return [equipment?.name ?? 'P&ID', label].filter(Boolean).join(' · ');
  }
  if (section === 'tags') return entryAt(project.tags, index)?.name ?? 'Variables';
  if (section === 'scenarios') return project.scenarios[Number(index)]?.name ?? 'Scénarios';
  return section === 'connections' ? 'Conduite du P&ID' : 'Connexion';
}

export function Readiness({ project, catalog, revision, enabled, onCorrect }: { project: Project; catalog: CatalogItem[]; revision: string; enabled: boolean; onCorrect: (target: Correction) => void }) {
  const [result, setResult] = useState<Validation | null>(null);
  const [pending, setPending] = useState(true);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!enabled) { setResult(null); setPending(false); return; }
    let active = true;
    const abort = new AbortController();
    setPending(true); setError('');
    const timer = setTimeout(async () => {
      try { const value = await api<Validation>('/validate/preview', 'POST', project, abort.signal); if (active) setResult(value); }
      catch (cause) { if (active) { setResult(null); setError(cause instanceof Error ? cause.message : String(cause)); } }
      finally { if (active) setPending(false); }
    }, 350);
    return () => { active = false; clearTimeout(timer); abort.abort(); };
  }, [project, revision, enabled, attempt]);
  const issue = (entry: Validation['errors'][number], index: number) => <button key={`${entry.path}:${index}`} className="readiness-issue" disabled={!enabled || pending} onClick={() => onCorrect(correctionFor(project, entry.path))}><span><strong>{titleFor(project, catalog, entry.path)}</strong><span>{entry.message}</span></span><ArrowRight size={16} /></button>;
  return <section className="readiness" role="region" aria-label="Préparer l’essai" aria-busy={pending}>
    <div className="readiness-heading">{pending ? <LoaderCircle size={18} className="spin" /> : result?.valid ? <CheckCircle2 size={18} /> : <CircleAlert size={18} />}<strong>{pending ? 'Vérification du brouillon…' : !enabled ? 'Vérification indisponible' : result?.valid ? 'Configuration locale prête' : 'Préparer l’essai'}</strong><small>{result?.valid && !pending ? (project.plc.mode === 'demo' ? 'Vous pouvez démarrer la démonstration.' : 'La connexion et les nœuds seront vérifiés avant les échanges.') : result && !pending ? `${result.errors.length} point(s) à corriger` : ''}</small></div>
    {!enabled && <p>Les corrections seront accessibles dès que le projet sera disponible.</p>}
    {error && <div className="readiness-error"><span>{error}</span><button className="button compact-button" onClick={() => setAttempt(value => value + 1)}>Revérifier</button></div>}
    {result && !pending && <><div className="readiness-list">{result.errors.slice(0, 4).map(issue)}</div>{result.errors.length > 4 && <details><summary>Voir les {result.errors.length - 4} autres points</summary>{result.errors.slice(4).map(issue)}</details>}{result.warnings.length > 0 && <details><summary>{result.warnings.length} conseil(s) de configuration</summary>{result.warnings.map(issue)}</details>}</>}
  </section>;
}
