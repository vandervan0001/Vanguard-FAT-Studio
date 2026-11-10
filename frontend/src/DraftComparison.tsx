import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { api, downloadText, getProjectRevision, getRunContext } from './api';
import { compareDraft, draftErrorKey, draftValue, mergeDraft, type DraftChange } from './draftMerge';
import type { LocalDraft } from './draftStore';
import type { Project, Validation } from './types';
import { useModalKeyboard } from './useModalKeyboard';
import './draft-comparison.css';

type Checked = Validation & { project: Project };
type Props = { project: Project; draft: LocalDraft; locked: boolean; onApply: (project: Project) => void; onClose: () => void };

export function DraftComparison({ project, draft, locked, onApply, onClose }: Props) {
  const [baseline] = useState(() => ({ project, revision: getProjectRevision(), run: getRunContext() }));
  const [changes, setChanges] = useState<DraftChange[]>([]);
  const [current, setCurrent] = useState<Checked | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const active = useRef(true);
  const applying = useRef<AbortController | null>(null);
  const stale = project !== baseline.project || getProjectRevision() !== baseline.revision || getRunContext() !== baseline.run;
  const disabled = locked || stale;
  const disabledRef = useRef(disabled); disabledRef.current = disabled;
  const separateNotes = Boolean(draft.scenario || draft.report.resultDirty || draft.report.marker || Object.keys(draft.observations).length);
  const downloadOriginal = () => downloadText(JSON.stringify(draft, null, 2), `${draft.project.id}-brouillon-complet.json`);
  useModalKeyboard(true, onClose);
  useEffect(() => {
    active.current = true;
    let alive = true;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    const prepare = async () => {
      try {
        if (!draft.baseProject) throw new Error('Ce brouillon ancien ne contient pas sa version de départ. Téléchargez-le pour conserver vos modifications.');
        const [base, local, saved] = await Promise.all([draft.baseProject, draft.project, baseline.project].map(value => api<Checked>('/validate/preview', 'POST', value, controller.signal, baseline.run)));
        if (!alive) return;
        if (getProjectRevision() !== baseline.revision || getRunContext() !== baseline.run) throw new Error('Le contexte a changé pendant la comparaison. Aucun champ n’a été repris.');
        const rows = compareDraft(base.project, local.project, saved.project);
        setChanges(rows); setCurrent(saved);
        // Conflicting values always require an explicit individual choice.
        setSelected(new Set(rows.filter(row => !row.conflict).map(row => row.key)));
      } catch (cause) { if (alive) setError(controller.signal.aborted ? 'La comparaison n’a pas abouti. Fermez cette fenêtre et réessayez quand le service répond.' : cause instanceof Error ? cause.message : String(cause)); }
      finally { clearTimeout(timer); if (alive) setBusy(false); }
    };
    void prepare();
    return () => { alive = false; active.current = false; clearTimeout(timer); controller.abort(); applying.current?.abort(); };
  }, [baseline, draft]);
  const apply = async () => {
    if (!current || disabledRef.current || !selected.size) return;
    setBusy(true); setError('');
    const controller = new AbortController(); applying.current = controller;
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const merged = mergeDraft(current.project, changes, selected);
      const checked = await api<Checked>('/validate/preview', 'POST', merged, controller.signal, baseline.run);
      if (!active.current) return;
      if (disabledRef.current || getProjectRevision() !== baseline.revision || getRunContext() !== baseline.run) throw new Error('Le contexte a changé. Le brouillon est conservé ; aucune fusion n’a été appliquée.');
      const existing = new Set(current.errors.map(item => draftErrorKey(current.project, item)));
      const addedErrors = checked.errors.filter(item => !existing.has(draftErrorKey(checked.project, item)));
      if (addedErrors.length) throw new Error('Ces choix créent des incohérences. Reprenez aussi les éléments liés ou retirez les choix concernés.\n' + addedErrors.map(item => `${item.path} : ${item.message}`).join('\n'));
      if (separateNotes) downloadOriginal();
      onApply(checked.project);
    } catch (cause) { if (active.current) setError(controller.signal.aborted ? 'La vérification n’a pas abouti. Aucun champ repris ; le brouillon est conservé.' : cause instanceof Error ? cause.message : String(cause)); }
    finally { clearTimeout(timer); if (applying.current === controller) applying.current = null; if (active.current) setBusy(false); }
  };
  return createPortal(<div className="modal-backdrop"><section className="modal draft-comparison-modal" role="dialog" aria-modal="true" aria-labelledby="draft-comparison-title">
    <div className="modal-heading"><h2 id="draft-comparison-title">Comparer le brouillon</h2><button className="icon-button" onClick={onClose} aria-label="Fermer la comparaison"><X size={18} /></button></div>
    <p>Choisissez les champs à reprendre. Les autres modifications de la version enregistrée sont conservées. Rien n’est enregistré sur le serveur avant « Enregistrer ».</p>
    {separateNotes && <p className="binding-notice">Le rapport, les observations et les étapes JSON non appliquées restent dans leur brouillon d’origine. Une copie complète sera téléchargée lors de la reprise ; ces notes ne sont pas fusionnées.</p>}
    {busy && <p role="status">Vérification des versions…</p>}
    {disabled && <p role="alert" className="inline-error">Le projet ou l’essai a changé, ou le service est indisponible. Fermez cette fenêtre et relisez le contexte ; votre brouillon est conservé.</p>}
    {error && <pre role="alert" className="inline-error">{error}</pre>}
    {current && <>
      <div className="button-row"><button className="button" disabled={busy || disabled} onClick={() => setSelected(new Set(changes.filter(row => !row.conflict).map(row => row.key)))}>Choisir les champs sans conflit</button><button className="button" disabled={busy || disabled} onClick={() => setSelected(new Set())}>Tout décocher</button><span>{selected.size} champ(s) choisi(s), {changes.filter(row => row.conflict).length} conflit(s)</span></div>
      <div className="draft-comparison-list">{changes.map(row => <article key={row.key} className={row.conflict ? 'has-conflict' : ''}>
        <label className="draft-change-choice"><input type="checkbox" checked={selected.has(row.key)} disabled={busy || disabled} onChange={event => setSelected(value => { const next = new Set(value); if (event.target.checked) next.add(row.key); else next.delete(row.key); return next; })} />{row.label}<span>{row.conflict ? 'Conflit à choisir' : ({ added: 'Ajout', removed: 'Suppression', changed: 'Modification' })[row.kind]}</span></label>
        <div className="draft-values"><div><strong>Au départ</strong><pre>{draftValue(row.before)}</pre></div><div><strong>Enregistré maintenant</strong><pre>{draftValue(row.current)}</pre></div><div><strong>Mon brouillon</strong><pre>{draftValue(row.local)}</pre></div></div>
      </article>)}{!changes.length && <p>Aucun changement du projet à reprendre. Vous pouvez conserver une copie du brouillon complet.</p>}</div>
    </>}
    <div className="modal-actions"><button className="button" onClick={downloadOriginal}>Télécharger le brouillon d’origine</button><button className="button" onClick={onClose}>Annuler</button><button className="button primary" disabled={busy || disabled || !current || !selected.size} onClick={() => void apply()}>Reprendre les champs choisis</button></div>
  </section></div>, document.body);
}
