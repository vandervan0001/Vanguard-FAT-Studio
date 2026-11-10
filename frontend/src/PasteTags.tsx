import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { FileUp, X } from 'lucide-react';
import { api } from './api';
import { MappingPreviewDetails, type MappingPreview } from './MappingImport';
import { useModalKeyboard } from './useModalKeyboard';
import type { Project, Tag } from './types';
import './paste-tags.css';

type Separator = 'auto' | 'tab' | 'semicolon' | 'comma';
type Analysis = { separator: Exclude<Separator, 'auto'>; columns: { index: number; header: string; suggested_field: string }[]; rows: { line: number; cells: string[] }[]; row_count: number };
type TablePreview = Omit<MappingPreview, 'project' | 'validation'> & { project: Project | null; validation: MappingPreview['validation'] | null; rows: { line: number; tag: Tag | null; errors: string[] }[]; generated_ids: boolean; separator: string };
type Props = { project: Project; locked: boolean; onChange: (update: (project: Project) => Project) => void; onClose: () => void; initialText?: string };
const FIELDS = [['', 'Ignorer cette colonne'], ['name', 'Nom'], ['direction', 'Sens automate'], ['data_type', 'Type'], ['id', 'Identifiant (fusion)'], ['unit', 'Unité'], ['initial_value', 'Valeur initiale'], ['min', 'Minimum'], ['max', 'Maximum'], ['node_id', 'NodeId OPC UA'], ['plc_address', 'Adresse Siemens'], ['plc_symbol', 'Symbole PLC'], ['writable', 'Écriture autorisée'], ['signal', 'Conversion analogique (JSON)'], ['_fat_csv_encoding', 'Encodage CSV Vanguard']] as const;
const SEPARATOR_LABELS = { tab: 'Tabulations', semicolon: 'Point-virgule', comma: 'Virgule' };

/** Keep the lossless Vanguard CSV import route for its three historical schemas. */
export function isCanonicalMappingCsv(text: string): boolean {
  const headers = text.replace(/^\uFEFF/, '').split(/\r?\n/, 1)[0].split(',').map(header => /^"[^"]*"$/.test(header) ? header.slice(1, -1) : header);
  if (new Set(headers).size !== headers.length) return false;
  const legacy = ['id', 'name', 'direction', 'data_type', 'unit', 'initial_value', 'min', 'max', 'node_id', 'writable'];
  return [legacy, [...legacy, 'plc_address', 'plc_symbol'], [...legacy, 'plc_address', 'plc_symbol', 'signal']].some(fields => [fields, [...fields, '_fat_csv_encoding']].some(expected => expected.length === headers.length && headers.every(header => expected.includes(header))));
}

export async function readTagTableFile(file: File): Promise<string> {
  if (file.size > 2_000_000) throw new Error('Le fichier est limité à 2 Mo.');
  const bytes = new Uint8Array(await file.arrayBuffer());
  const encoding = bytes[0] === 0xff && bytes[1] === 0xfe ? 'utf-16le' : bytes[0] === 0xfe && bytes[1] === 0xff ? 'utf-16be' : 'utf-8';
  try { return new TextDecoder(encoding, { fatal: true }).decode(bytes); }
  catch { throw new Error('Encodage illisible. Exportez le tableau en CSV UTF-8 ou copiez les cellules depuis Excel. Les fichiers texte UTF-16 avec marqueur sont aussi acceptés.'); }
}

export function PasteTags({ project, locked, onChange, onClose, initialText = '' }: Props) {
  const [base] = useState(project);
  const [text, setText] = useState(initialText);
  const [separator, setSeparator] = useState<Separator>('auto');
  const [hasHeader, setHasHeader] = useState(true);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [columns, setColumns] = useState<string[]>([]);
  const [commonDirection, setCommonDirection] = useState('');
  const [commonType, setCommonType] = useState('');
  const [mode, setMode] = useState<'merge' | 'replace'>('merge');
  const [preview, setPreview] = useState<TablePreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const request = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const stale = project !== base;
  const disabled = locked || stale;
  useModalKeyboard(true, onClose);
  useEffect(() => () => { sequence.current++; request.current?.abort(); }, []);

  function invalidate(source = false) {
    sequence.current++; request.current?.abort(); setBusy(false); setError(''); setPreview(null);
    if (source) { setAnalysis(null); setColumns([]); setCommonDirection(''); setCommonType(''); }
  }
  async function prepare(kind: 'analyze' | 'preview') {
    if (disabled || busy) return;
    const ticket = ++sequence.current;
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    setBusy(true); setError(''); setPreview(null);
    if (kind === 'analyze') setAnalysis(null);
    try {
      if (new TextEncoder().encode(text).length > 2_000_000) throw new Error('Le tableau est limité à 2 Mo de texte UTF-8.');
      const body = { project: base, text, separator: kind === 'preview' ? analysis!.separator : separator, has_header: hasHeader };
      if (kind === 'analyze') {
        const result = await api<Analysis>('/mapping/table/analyze', 'POST', body, controller.signal);
        if (sequence.current === ticket) { setAnalysis(result); setColumns(result.columns.map(column => column.suggested_field)); }
      } else {
        const defaults = { ...(!columns.includes('direction') && commonDirection ? { direction: commonDirection } : {}), ...(!columns.includes('data_type') && commonType ? { data_type: commonType } : {}) };
        const result = await api<TablePreview>('/mapping/table/preview', 'POST', { ...body, columns, mode, defaults }, controller.signal);
        if (sequence.current === ticket) setPreview(result);
      }
    } catch (error) { if (sequence.current === ticket && !controller.signal.aborted) setError(error instanceof Error ? error.message : String(error)); }
    finally { if (sequence.current === ticket) setBusy(false); }
  }
  async function readFile(file: File | undefined) {
    if (!file || disabled || busy) return;
    invalidate(true);
    const ticket = sequence.current;
    try {
      const value = await readTagTableFile(file);
      if (sequence.current === ticket) setText(value);
    } catch (error) { if (sequence.current === ticket) setError(error instanceof Error ? error.message : String(error)); }
  }
  const missingFields = ['name', 'direction', 'data_type'].filter(field => !columns.includes(field) && !(field === 'direction' ? commonDirection : field === 'data_type' ? commonType : false));
  const duplicateFields = columns.filter(Boolean).length !== new Set(columns.filter(Boolean)).size;
  return createPortal(<div className="modal-backdrop"><section className="modal paste-tags-modal" role="dialog" aria-modal="true" aria-labelledby="paste-tags-title">
    <div className="modal-heading"><h2 id="paste-tags-title">Coller des tags Excel</h2><button className="icon-button" aria-label="Fermer le collage des tags" onClick={onClose}><X size={18} /></button></div>
    <div className="paste-tags-scroll">
    <p>Copiez les cellules depuis Excel, titres compris, ou ouvrez un fichier CSV/TSV. Relisez les colonnes puis les variables avant application.</p>
    <label>Tableau de tags<textarea className="mono" aria-label="Tableau de tags" spellCheck={false} rows={5} value={text} readOnly={disabled || busy} placeholder={'Nom\tSens\tType\tValeur initiale\nP101_Running\tinput\tBOOL\tfalse'} onChange={event => { invalidate(true); setText(event.target.value); }} /></label>
    <div className="paste-tags-toolbar">
      <input ref={fileInput} aria-label="Fichier texte du tableau" type="file" accept=".csv,.tsv,.txt,text/csv,text/tab-separated-values,text/plain" hidden onChange={event => { void readFile(event.target.files?.[0]); event.target.value = ''; }} />
      <button className="button" disabled={disabled || busy} onClick={() => fileInput.current?.click()}><FileUp size={16} />Ouvrir un fichier CSV ou TSV</button>
      <label>Séparateur<select aria-label="Séparateur du tableau" value={separator} disabled={disabled || busy} onChange={event => { invalidate(true); setSeparator(event.target.value as Separator); }}><option value="auto">Détection automatique</option>{Object.entries(SEPARATOR_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className="paste-tags-checkbox"><input type="checkbox" checked={hasHeader} disabled={disabled || busy} onChange={event => { invalidate(true); setHasHeader(event.target.checked); }} />La première ligne contient les titres</label>
      <button className="button primary" disabled={disabled || busy || !text.trim()} onClick={() => void prepare('analyze')}>Analyser le tableau</button>
    </div>
    {disabled && <p className="inline-error" role="alert">{stale ? 'Le projet a changé. Copiez votre tableau avant de fermer cette fenêtre, puis relisez le projet.' : 'Le projet est verrouillé. Votre tableau reste visible.'}</p>}
    {busy && <p role="status">Préparation du tableau…</p>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    {analysis && <section aria-label="Correspondance des colonnes" className="paste-tags-columns">
      <h3>Relire les colonnes</h3>
      <p>{analysis.row_count} ligne(s) · {SEPARATOR_LABELS[analysis.separator]}. Les suggestions viennent des titres. Le sens est celui de l’automate : input/entrée ou output/sortie. Types acceptés : BOOL, INT, DINT, REAL.</p>
      <div className="paste-tags-column-grid">{analysis.columns.map(column => <label key={column.index}><strong>{column.header}</strong><small>{analysis.rows.slice(0, 3).map(row => row.cells[column.index] || '∅').join(' · ')}</small><select aria-label={`Colonne ${column.index + 1} : ${column.header}`} value={columns[column.index] ?? ''} disabled={disabled || busy} onChange={event => { invalidate(); const value = event.target.value; setColumns(current => current.map((field, index) => index === column.index ? value : field)); if (value === 'direction') setCommonDirection(''); if (value === 'data_type') setCommonType(''); }}>{FIELDS.map(([field, label]) => <option key={field} value={field}>{label}</option>)}</select></label>)}</div>
      {(!columns.includes('direction') || !columns.includes('data_type')) && <div className="paste-tags-common"><p>Une colonne manque ? Choisissez explicitement une valeur commune à toutes les lignes.</p><div className="paste-tags-toolbar">
        {!columns.includes('direction') && <label>Sens commun<select aria-label="Sens commun à toutes les lignes" disabled={disabled || busy} value={commonDirection} onChange={event => { invalidate(); setCommonDirection(event.target.value); }}><option value="">Choisir le sens</option><option value="input">Entrée simulée → PLC (input)</option><option value="output">Commande PLC → modèle (output)</option></select></label>}
        {!columns.includes('data_type') && <label>Type commun<select aria-label="Type commun à toutes les lignes" disabled={disabled || busy} value={commonType} onChange={event => { invalidate(); setCommonType(event.target.value); }}><option value="">Choisir le type</option>{['BOOL', 'INT', 'DINT', 'REAL'].map(type => <option key={type} value={type}>{type}</option>)}</select></label>}
      </div></div>}
      {missingFields.length > 0 && <p className="inline-error">Associez Nom, Sens automate et Type, ou choisissez les valeurs communes manquantes.</p>}
      {duplicateFields && <p className="inline-error" role="alert">Un champ ne peut correspondre qu’à une seule colonne.</p>}
      <p className="small-muted">Sans colonne Identifiant, chaque ligne crée une variable avec un identifiant neuf. Avec un identifiant existant, les champs absents du tableau sont conservés. Pour une nouvelle variable : valeur initiale 0 ou false, écriture désactivée si ces colonnes sont absentes. Aucune adresse Siemens n’est convertie en NodeId.</p>
      <div className="paste-tags-toolbar"><label>Mode d’import<select aria-label="Mode d’import du tableau" value={mode} disabled={disabled || busy} onChange={event => { invalidate(); setMode(event.target.value as 'merge' | 'replace'); }}><option value="merge">Fusionner et conserver les autres variables</option><option value="replace">Remplacer la liste des variables</option></select></label><button className="button primary" disabled={disabled || busy || Boolean(missingFields.length) || duplicateFields} onClick={() => void prepare('preview')}>Préparer l’aperçu</button></div>
    </section>}
    {preview && <section aria-label="Aperçu des tags collés"><h3>Relire les variables</h3>
      {preview.generated_ids && <p>Les identifiants ci-dessous sont neufs ; aucune correspondance par nom n’a été appliquée.</p>}
      <div className="paste-tags-result-table" tabIndex={0} aria-label="Variables préparées"><table><thead><tr><th>Ligne</th><th>Nom / identifiant</th><th>Sens</th><th>Type</th><th>Valeur initiale</th><th>Écriture</th></tr></thead><tbody>{preview.rows.map(row => <tr key={row.line} className={row.errors.length ? 'invalid-row' : ''}><td>{row.line}</td>{row.tag ? <><td>{row.tag.name}<small>{row.tag.id}</small>{row.tag.node_id && <small>NodeId : {row.tag.node_id}</small>}</td><td>{row.tag.direction === 'input' ? 'Entrée automate' : 'Sortie automate'}</td><td>{row.tag.data_type}</td><td>{String(row.tag.initial_value)}</td><td>{row.tag.writable ? 'Autorisée' : 'Désactivée'}</td></> : <td colSpan={5}>{row.errors.join(' ; ')}</td>}</tr>)}</tbody></table></div>
      <MappingPreviewDetails preview={preview} />
    </section>}
    </div>
    <div className="modal-actions"><button className="button" onClick={onClose}>Annuler</button><button className="button primary" disabled={disabled || busy || !preview?.project || !preview.changes.length || Boolean(preview.errors.length)} onClick={() => { if (preview?.project && !disabled && !preview.errors.length) { const next = preview.project; onChange(current => current === base ? next : current); onClose(); } }}>Appliquer l’import au brouillon</button></div>
    <p className="small-muted">L’application modifie le brouillon. Enregistrez le projet pour conserver l’import.</p>
  </section></div>, document.body);
}
