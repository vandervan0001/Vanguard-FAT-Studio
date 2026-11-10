import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { api } from './api';
import { useModalKeyboard } from './useModalKeyboard';
import type { Project, Validation } from './types';
import './tag-workflow.css';

type Preview = { project: Project; changes: { id: string; name: string; kind: 'added' | 'changed' | 'removed'; fields: string[]; blocked: boolean; reasons: string[] }[]; errors: string[]; validation: Validation };
type Props = { project: Project; csv: string; locked: boolean; onChange: (update: (project: Project) => Project) => void; onClose: () => void };
const FIELD_LABELS: Record<string, string> = { name: 'Nom', direction: 'Sens', data_type: 'Type', unit: 'Unité', initial_value: 'Valeur initiale', min: 'Minimum', max: 'Maximum', node_id: 'NodeId OPC UA', writable: 'Droit d’écriture', plc_address: 'Adresse Siemens', plc_symbol: 'Symbole PLC', signal: 'Conversion analogique' };

export function MappingImport({ project, csv, locked, onChange, onClose }: Props) {
  const [base] = useState(project);
  const [mode, setMode] = useState<'merge' | 'replace'>('merge');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(true);
  const sequence = useRef(0);
  const stale = project !== base;
  const disabled = locked || stale;
  useModalKeyboard(true, onClose);
  useEffect(() => {
    const ticket = ++sequence.current;
    setBusy(true); setError(''); setPreview(null);
    void api<Preview>('/mapping/preview', 'POST', { csv, mode, project: base }).then(data => { if (sequence.current === ticket) setPreview(data); }).catch(error => { if (sequence.current === ticket) setError(error instanceof Error ? error.message : String(error)); }).finally(() => { if (sequence.current === ticket) setBusy(false); });
    return () => { sequence.current++; };
  }, [base, csv, mode]);
  return createPortal(<div className="modal-backdrop"><section className="modal mapping-import-modal" role="dialog" aria-modal="true" aria-labelledby="mapping-import-title">
    <div className="modal-heading"><h2 id="mapping-import-title">Relire l’import des variables</h2><button className="icon-button" aria-label="Fermer l’import des variables" onClick={onClose}><X size={18} /></button></div>
    <label>Mode d’import<select disabled={disabled || busy} value={mode} onChange={event => setMode(event.target.value as 'merge' | 'replace')}><option value="merge">Fusionner par identifiant et conserver les autres variables</option><option value="replace">Remplacer la liste des variables</option></select></label>
    <p>La fusion met à jour les identifiants présents dans le CSV et ajoute les nouveaux. Les associations et scénarios sont conservés. Les changements restent dans le brouillon jusqu’à l’enregistrement du projet.</p>
    {busy && <p role="status">Préparation de l’aperçu…</p>}
    {disabled && <p className="inline-error" role="alert">{stale ? 'Le projet a changé. Fermez cet aperçu et relisez le projet avant de refaire l’import.' : 'Le projet est verrouillé. L’aperçu reste visible.'}</p>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    {preview && <><p className="binding-notice" role="status">{preview.changes.filter(row => row.kind === 'added').length} ajout(s), {preview.changes.filter(row => row.kind === 'changed').length} modification(s), {preview.changes.filter(row => row.kind === 'removed').length} suppression(s).</p>
      <div className="mapping-preview-list">{preview.changes.map(row => <article key={row.id} className={row.blocked ? 'blocked' : ''}><strong>{row.name}</strong><small>{row.id} · {({ added: 'Ajout', changed: 'Modification', removed: 'Suppression' })[row.kind]}{row.fields.length ? ` · ${row.fields.map(field => FIELD_LABELS[field] ?? field).join(', ')}` : ''}</small>{row.reasons.map(reason => <p key={reason}>{reason}</p>)}</article>)}{!preview.changes.length && <p>Le CSV ne change aucune variable.</p>}</div>
      {preview.errors.length > 0 && <div className="inline-error" role="alert">{preview.errors.map(message => <p key={message}>{message}</p>)}</div>}
      {!preview.validation.valid && <p className="small-muted">Le projet comporte encore {preview.validation.errors.length} point(s) à corriger avant un essai. Consultez « Prêt pour l’essai » après application.</p>}
    </>}
    <div className="modal-actions"><button className="button" onClick={onClose}>Annuler</button><button className="button primary" disabled={disabled || busy || !preview || !preview.changes.length || Boolean(preview.errors.length)} onClick={() => { if (preview && !disabled && !preview.errors.length) { onChange(current => current === base ? preview.project : current); onClose(); } }}>Appliquer l’import au brouillon</button></div>
  </section></div>, document.body);
}
