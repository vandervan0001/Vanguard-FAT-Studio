import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { BookOpen, X } from 'lucide-react';
import { api, downloadText } from './api';
import { CIRCUIT_LIBRARY_KEY, importSavedCircuits, insertSavedCircuit, makeSavedCircuit, parseSavedCircuits, planLibraryImport, readSavedCircuits, removeSavedCircuit, saveCircuit, type SavedCircuit } from './circuitLibrary';
import { isFlowEquipment } from './processCircuits';
import { useModalKeyboard } from './useModalKeyboard';
import type { CatalogItem, Project, Validation } from './types';
import './flow-library.css';

type Props = { project: Project; catalog: CatalogItem[]; locked: boolean; mode: 'browse' | 'save'; equipmentId?: string;
  onApply: (base: Project, next: Project, ids: string[]) => void; onClose: () => void };
export function CircuitLibrary({ project, catalog, locked, mode, equipmentId, onApply, onClose }: Props) {
  const [base] = useState(project);
  const [entries, setEntries] = useState<SavedCircuit[]>([]);
  const [selected, setSelected] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [storageError, setStorageError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [prepared, setPrepared] = useState<{ project: Project; ids: string[]; warnings: string[] } | null>(null);
  const [importPreview, setImportPreview] = useState<{ entries: SavedCircuit[]; expectedRaw: string | null; unchanged: number } | null>(null);
  const importInput = useRef<HTMLInputElement>(null);
  const latest = useRef({ project, locked }); latest.current = { project, locked };
  const mounted = useRef(true);
  const stale = project !== base;
  const disabled = locked || stale || busy;
  const anchor = base.equipment.find(item => item.id === equipmentId && isFlowEquipment(item));
  const entry = entries.find(item => item.id === selected);
  const refresh = () => {
    try { const values = readSavedCircuits(); setEntries(values); setStorageError(''); setSelected(current => values.some(item => item.id === current) ? current : values[0]?.id ?? ''); }
    catch (error) { setEntries([]); setStorageError(error instanceof Error ? error.message : String(error)); }
  };
  useEffect(() => {
    mounted.current = true; refresh();
    const changed = (event: StorageEvent) => { if (event.key === CIRCUIT_LIBRARY_KEY || event.key === null) { refresh(); setPrepared(null); setImportPreview(null); } };
    window.addEventListener('storage', changed);
    return () => { mounted.current = false; window.removeEventListener('storage', changed); };
  }, []);
  useModalKeyboard(true, onClose);
  const current = () => mounted.current && latest.current.project === base && !latest.current.locked;
  const act = async (operation: () => Promise<void>) => {
    if (disabled) return;
    setBusy(true); setError(''); setMessage('');
    try { await operation(); } catch (error) { if (mounted.current) setError(error instanceof Error ? error.message : String(error)); }
    finally { if (mounted.current) setBusy(false); }
  };
  const prepare = () => act(async () => {
    if (!entry) return;
    const source = await api<Validation & { project: Project }>('/validate/preview', 'POST', {
      ...base, plc: { ...base.plc, mode: 'demo' }, equipment: entry.equipment, tags: entry.tags, connections: entry.connections, scenarios: [],
    });
    if (!current()) throw new Error('Le projet a changé pendant la vérification. Fermez cet aperçu et relisez le projet.');
    if (!source.valid) throw new Error(`Le modèle personnel est incomplet : ${source.errors.slice(0, 4).map(item => item.message).join(' ; ')}`);
    const planned = insertSavedCircuit(base, catalog, { ...entry, equipment: source.project.equipment, tags: source.project.tags, connections: source.project.connections });
    const checked = await api<Validation & { project: Project }>('/validate/preview', 'POST', planned.project);
    if (!current()) throw new Error('Le projet a changé pendant la vérification. Fermez cet aperçu et relisez le projet.');
    setPrepared({ project: checked.project, ids: planned.selectedIds, warnings: checked.errors.map(item => item.message) });
  });
  const save = () => act(async () => {
    if (!anchor || storageError) return;
    const saved = makeSavedCircuit(base, catalog, anchor.id, name);
    const checked = await api<Validation & { project: Project }>('/validate/preview', 'POST', {
      ...base, plc: { ...base.plc, mode: 'demo' }, equipment: saved.equipment, tags: saved.tags, connections: saved.connections, scenarios: [],
    });
    if (!current()) throw new Error('Le projet a changé pendant la vérification. Aucun modèle enregistré.');
    if (!checked.valid) throw new Error(`Complétez ce circuit avant de l’enregistrer : ${checked.errors.slice(0, 4).map(item => item.message).join(' ; ')}`);
    saveCircuit(saved); refresh(); setMessage(`« ${saved.name} » est enregistré dans votre bibliothèque locale.`); setName('');
  });
  const remove = () => {
    if (!entry || disabled || !window.confirm(`Supprimer « ${entry.name} » de votre bibliothèque ? Les circuits déjà insérés dans les projets seront conservés.`)) return;
    try { removeSavedCircuit(entry.id); setPrepared(null); refresh(); setError(''); } catch (error) { setError(error instanceof Error ? error.message : String(error)); }
  };
  const reviewImport = (file: File) => act(async () => {
    setImportPreview(null);
    if (file.size > 2 * 1024 * 1024) throw new Error('Le fichier de bibliothèque est limité à 2 Mio.');
    const expectedRaw = localStorage.getItem(CIRCUIT_LIBRARY_KEY);
    const incoming = parseSavedCircuits(await file.text());
    const plan = planLibraryImport(readSavedCircuits(), incoming);
    for (const item of plan.additions) {
      const checked = await api<Validation & { project: Project }>('/validate/preview', 'POST', {
        ...base, plc: { ...base.plc, mode: 'demo' }, equipment: item.equipment, tags: item.tags, connections: item.connections, scenarios: [],
      });
      if (!current()) throw new Error('Le projet a changé pendant la vérification. Aucun modèle importé.');
      if (!checked.valid) throw new Error(`Le circuit « ${item.name} » est incomplet : ${checked.errors.slice(0, 3).map(issue => issue.message).join(' ; ')}`);
    }
    if (!current() || localStorage.getItem(CIRCUIT_LIBRARY_KEY) !== expectedRaw) throw new Error('Le projet ou la bibliothèque a changé. Relisez le fichier avant de l’importer.');
    setImportPreview({ entries: plan.additions, expectedRaw, unchanged: plan.unchanged });
  });
  return createPortal(<div className="modal-backdrop"><section className="modal saved-circuit-modal" role="dialog" aria-modal="true" aria-labelledby="saved-circuit-title">
    <div className="modal-heading"><h2 id="saved-circuit-title">{mode === 'save' ? 'Enregistrer mon circuit' : 'Mes circuits'}</h2><button className="icon-button" aria-label="Fermer ma bibliothèque de circuits" onClick={onClose}><X size={18} /></button></div>
    <p>Vos modèles restent dans ce navigateur, à cette adresse locale. Ils sont disponibles dans vos autres projets ouverts ici. Exportez la bibliothèque pour en conserver une copie.</p>
    {storageError && <div className="inline-error" role="alert"><p>{storageError}</p><button className="button" disabled={disabled} onClick={() => { if (window.confirm('Effacer la bibliothèque locale illisible ? Téléchargez d’abord une copie si vous souhaitez la conserver. Les projets resteront inchangés.')) { try { localStorage.removeItem(CIRCUIT_LIBRARY_KEY); refresh(); } catch { setError('Le navigateur ne peut pas effacer cette bibliothèque.'); } } }}>Effacer la bibliothèque illisible</button></div>}
    {mode === 'save' ? <>
      <p>{anchor ? `Le circuit de ${anchor.name}, ses cuves, ses capteurs et ses conduites seront conservés ensemble.` : 'Sélectionnez une pompe ou une vanne pour enregistrer son circuit.'}</p>
      <label>Nom du circuit<input aria-label="Nom du circuit" maxLength={200} disabled={disabled || Boolean(storageError)} value={name} onChange={event => setName(event.target.value)} placeholder="Ex. Transfert cuve tampon" /></label>
      <p className="small-muted">Les NodeIds, adresses et symboles PLC sont effacés. La connexion automate, les scénarios et les preuves d’essais ne sont pas enregistrés dans ce modèle.</p>
    </> : <>
      {entries.length ? <><label>Modèle personnel<select aria-label="Modèle personnel" disabled={disabled} value={selected} onChange={event => { setSelected(event.target.value); setPrepared(null); setError(''); }}>{entries.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        {entry && <div className="saved-circuit-preview" aria-label="Contenu du modèle"><strong>{entry.name}</strong><p>{entry.equipment.length} équipement(s), {entry.tags.length} tag(s), {entry.connections.length} conduite(s).</p><ul>{entry.equipment.map(item => <li key={item.id}>{item.name}</li>)}</ul><p>La copie reçoit de nouveaux repères et identifiants. Ses adresses automate restent vides ; les associations internes sont conservées.</p><button className="danger-text" disabled={disabled} onClick={remove}>Supprimer ce modèle</button></div>}
      </> : !storageError && <div className="saved-circuit-empty"><BookOpen size={28} /><p>Votre bibliothèque est vide. Sélectionnez une pompe ou une vanne dans le P&ID, puis « Enregistrer ce circuit ».</p></div>}
      {prepared && <div className="binding-notice" role="status"><strong>Copie vérifiée : {prepared.ids.length} équipement(s) à ajouter au brouillon.</strong>{prepared.warnings.length > 0 && <p>Le projet contient encore {prepared.warnings.length} point(s) à corriger avant un essai. Consultez « Prêt pour l’essai » après l’application.</p>}</div>}
    </>}
    {message && <p className="binding-notice" role="status">{message}</p>}
    {importPreview && <div className="saved-circuit-preview" aria-label="Aperçu de l’import de circuits"><strong>{importPreview.entries.length} modèle(s) à ajouter, {importPreview.unchanged} déjà présent(s).</strong><ul>{importPreview.entries.map(item => <li key={item.id}>{item.name}</li>)}</ul><p>Les modèles actuels seront conservés. Les adresses automate des modèles importés sont effacées.</p><div className="button-row"><button className="button" onClick={() => setImportPreview(null)}>Annuler l’import</button><button className="button primary" disabled={disabled || !importPreview.entries.length} onClick={() => { if (!current()) return; try { importSavedCircuits(importPreview.entries, importPreview.expectedRaw); refresh(); setImportPreview(null); setMessage('Les modèles sont ajoutés à votre bibliothèque locale.'); } catch (error) { setError(error instanceof Error ? error.message : String(error)); } }}>Importer ces modèles</button></div></div>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    {locked || stale ? <p className="inline-error" role="alert">{stale ? 'Le projet a changé. Fermez cet aperçu et relisez le projet.' : 'Le projet est verrouillé. Votre sélection est conservée.'}</p> : null}
    <input ref={importInput} type="file" accept=".json,application/json" hidden onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; if (file) void reviewImport(file); }} />
    <div className="modal-actions"><button className="button" onClick={onClose}>Fermer</button><button className="button" disabled={disabled || Boolean(storageError)} onClick={() => importInput.current?.click()}>Importer une bibliothèque</button><button className="button" onClick={() => { try { downloadText(localStorage.getItem(CIRCUIT_LIBRARY_KEY) ?? '[]', 'vanguard-mes-circuits.json'); } catch { setError('Le navigateur ne peut pas lire la bibliothèque.'); } }}>Exporter la bibliothèque</button>
      {mode === 'save' ? <button className="button primary" disabled={disabled || !anchor || !name.trim() || Boolean(storageError)} onClick={() => void save()}>Enregistrer dans ma bibliothèque</button>
        : prepared ? <button className="button primary" disabled={disabled} onClick={() => { if (current()) { onApply(base, prepared.project, prepared.ids); onClose(); } }}>Appliquer la copie au brouillon</button>
          : <button className="button primary" disabled={disabled || !entry} onClick={() => void prepare()}>{busy ? 'Vérification…' : 'Préparer la copie'}</button>}
    </div>
  </section></div>, document.body);
}
