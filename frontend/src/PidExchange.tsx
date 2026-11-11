import { useEffect, useRef, useState } from 'react';
import { ArrowDownToLine, BookOpen, Check, CircleAlert, ExternalLink, FileSearch, LayoutTemplate, LoaderCircle, Upload, X } from 'lucide-react';
import { api, downloadPid, downloadText } from './api';
import { useModalKeyboard } from './useModalKeyboard';
import type { CatalogItem, PidCapabilities, PidCatalog, PidDocument, PidDrawingPreview, PidDrawingSettings, Project } from './types';
import PidDrawingEditor, { drawingDefaults, drawingValidation } from './PidDrawingEditor';
import PidConventionsGuide from './PidConventionsGuide';
import './pid-exchange.css';

type Props = {
  open: boolean; project: Project; catalog: CatalogItem[]; contextKey: string;
  applyBlocked: string; exportBlocked: string; onClose: () => void;
  onApply: (project: Project, contextKey: string) => void;
  drawingBlocked: string; previewBlocked: string;
  onApplyDrawing: (settings: PidDrawingSettings, contextKey: string, projectId: string) => void;
  onSaveDrawing: (settings: PidDrawingSettings, contextKey: string, projectId: string) => Promise<{ settings: PidDrawingSettings; contextKey: string; projectId: string }>;
  onDrawingPendingChange: (pending: boolean) => void;
};
type Prepared = { project: Project; warnings: string[]; contextKey: string };
const message = (error: unknown) => error instanceof Error ? error.message : String(error);
const confidence = (value: number) => `${Math.round(value * 100)} % estimés`;
const safeLink = (value: string) => /^https?:\/\//i.test(value) ? value : undefined;

export default function PidExchange({ open, project, catalog, contextKey, applyBlocked, exportBlocked, drawingBlocked, previewBlocked, onClose, onApply, onApplyDrawing, onSaveDrawing, onDrawingPendingChange }: Props) {
  const [tab, setTab] = useState<'import' | 'export' | 'catalog' | 'drawing'>('import');
  const [capabilities, setCapabilities] = useState<PidCapabilities | null>(null);
  const [sources, setSources] = useState<PidCatalog | null>(null);
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [pages, setPages] = useState('');
  const [ocr, setOcr] = useState(false);
  const [working, setWorking] = useState('');
  const [document, setDocument] = useState<PidDocument | null>(null);
  const [selection, setSelection] = useState<string[]>([]);
  const [types, setTypes] = useState<Record<string, string>>({});
  const [connections, setConnections] = useState<string[]>([]);
  const [name, setName] = useState('');
  const [query, setQuery] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [reviewed, setReviewed] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [prepared, setPrepared] = useState<Prepared | null>(null);
  const [drawingDraft, setDrawingDraft] = useState(() => {
    const settings = drawingDefaults(project.pid_drawing);
    return { settings, projectId: project.id, contextKey, base: JSON.stringify(settings), edited: false };
  });
  const [drawingPreview, setDrawingPreview] = useState<{ result: PidDrawingPreview; settings: string; contextKey: string; projectId: string } | null>(null);
  const contextRef = useRef(contextKey);
  contextRef.current = contextKey;
  useModalKeyboard(open, onClose);

  useEffect(() => {
    if (!open) { setFile(null); return; }
    const controller = new AbortController();
    setLoading(true); setError('');
    void Promise.all([
      api<PidCapabilities>('/pid/capabilities', 'GET', undefined, controller.signal),
      api<PidCatalog>('/pid/catalog', 'GET', undefined, controller.signal),
    ]).then(([available, catalogData]) => {
      if (!controller.signal.aborted) { setCapabilities(available); setSources(catalogData); }
    }).catch(error => { if (!controller.signal.aborted) setError(message(error)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [open, attempt]);

  useEffect(() => { setPrepared(null); setConfirmed(false); }, [contextKey]);
  useEffect(() => {
    setDrawingDraft(current => {
      if (current.edited) return current;
      const settings = drawingDefaults(project.pid_drawing);
      const base = JSON.stringify(settings);
      return current.projectId === project.id && current.contextKey === contextKey && current.base === base ? current : { settings, base, projectId: project.id, contextKey, edited: false };
    });
  }, [project.id, project.pid_drawing, contextKey]);
  useEffect(() => { onDrawingPendingChange(drawingDraft.edited); }, [drawingDraft.edited, onDrawingPendingChange]);

  const invalidate = () => { setPrepared(null); setConfirmed(false); setReviewed(false); setNotice(''); };
  const maxEquipment = capabilities?.limits.max_equipment ?? 50;
  const maxConnections = capabilities?.limits.max_connections ?? 200;
  const symbols = catalog.find(item => item.type === 'pid_symbol')?.symbols ?? [];
  const models = catalog.filter(item => item.type !== 'pid_symbol');
  const selected = new Set(selection);
  const availableConnections = document?.connections.filter(item => selected.has(item.source) && selected.has(item.target)) ?? [];
  const keptConnections = availableConnections.filter(item => connections.includes(item.id));
  const unresolved = selection.filter(id => !models.some(item => item.type === types[id]) && !symbols.some(item => `pid:${item.id}` === types[id]));
  const equipmentById = new Map(document?.equipment.map(item => [item.id, item]) ?? []);
  const filteredEquipment = document?.equipment.filter(item => `${item.id} ${item.name} ${item.source_tag}`.toLocaleLowerCase().includes(query.toLocaleLowerCase())) ?? [];
  const sourcePage = document?.pages[pageIndex];
  const portsToReview = keptConnections.flatMap(connection => (['source', 'target'] as const).flatMap(side => {
    const port = side === 'source' ? connection.source_port : connection.target_port;
    const choice = types[connection[side]];
    if (!port || !choice?.startsWith('pid:')) return [];
    const definition = symbols.find(symbol => `pid:${symbol.id}` === choice);
    return definition?.ports.some(item => item.id === port) ? [] : [`${equipmentById.get(connection[side])?.name ?? connection[side]} · ${port}`];
  }));
  const preparedCurrent = prepared?.contextKey === contextKey ? prepared : null;
  const drawingMismatch = drawingDraft.projectId !== project.id || drawingDraft.contextKey !== contextKey;
  const drawingError = drawingValidation(drawingDraft.settings);
  const currentExportBlocked = drawingDraft.edited ? 'Enregistrez la mise en page avant d’exporter le P&ID. Votre brouillon est conservé dans l’onglet Mise en page.' : exportBlocked;
  const cannotPrepare = applyBlocked || (!selection.length ? 'Sélectionnez au moins un équipement.'
    : selection.length > maxEquipment ? `Limitez la sélection à ${maxEquipment} équipements.`
      : unresolved.length ? `Choisissez le type FAT de ${unresolved.length} équipement(s) sélectionné(s).`
        : keptConnections.length > maxConnections ? `Limitez la sélection à ${maxConnections} connexions.`
          : !name.trim() ? 'Nommez le nouveau projet.' : !reviewed ? 'Confirmez la revue des équipements et des connexions.' : '');

  const reviewDocument = (result: PidDocument, fromProject = false) => {
    const current = new Map(fromProject ? project.equipment.map(item => [item.id, item]) : []);
    const retained = result.equipment.filter(item => current.has(item.id));
    setDocument(result); setName((fromProject ? project.name : result.title).slice(0, 120)); setPageIndex(0); setQuery('');
    setSelection((fromProject && retained.length ? retained : result.equipment).slice(0, maxEquipment).map(item => item.id));
    setTypes(Object.fromEntries(result.equipment.map(item => {
      const saved = current.get(item.id);
      const symbolType = item.type === 'valve_three_way' ? 'three_way_valve' : item.type;
      const documentaryChoice = `pid:${symbols.some(symbol => symbol.id === symbolType) ? symbolType : 'generic'}`;
      const value = saved ? saved.type === 'pid_symbol' ? `pid:${saved.symbol_kind || 'generic'}` : saved.type
        : item.documentary || ['heat_exchanger', 'valve_three_way'].includes(item.type) ? documentaryChoice
          : models.some(kind => kind.type === item.type) ? item.type : documentaryChoice;
      return [item.id, value];
    })));
    setConnections(result.connections.map(item => item.id)); invalidate(); setTab('import');
    setNotice(fromProject ? 'Document source rouvert depuis le projet. Le schéma peut avoir été modifié depuis son import ; comparez-le à la source.' : 'Document inspecté. Vérifiez les repères, les types et les connexions avant de préparer un projet.');
  };

  const inspect = async () => {
    if (!file || working) return;
    const uploadMb = capabilities?.limits.upload_mb ?? 20;
    if (file.size > uploadMb * 1024 * 1024) { setError(`Le fichier dépasse ${uploadMb} Mo. Choisissez une version plus légère.`); return; }
    setWorking('Inspection locale du document…'); setError(''); setNotice('');
    try {
      const params = new URLSearchParams({ filename: file.name, pages: pages.trim(), ocr: String(ocr) });
      const result = await api<PidDocument>(`/pid/inspect?${params}`, 'POST', file);
      reviewDocument(result);
    } catch (error) { setError(message(error)); }
    finally { setWorking(''); }
  };

  const prepare = async () => {
    if (!document || cannotPrepare || working) return;
    const expectedContext = contextKey;
    setWorking('Préparation du brouillon…'); setError(''); setPrepared(null); setConfirmed(false);
    try {
      const result = await api<{ project: Project; warnings: string[] }>('/pid/prepare', 'POST', {
        document: { ...document, connections: keptConnections }, selected_ids: selection, types, name: name.trim(),
      });
      if (contextRef.current !== expectedContext) throw new Error('Le contexte du projet a changé pendant la préparation. Votre revue est conservée ; préparez à nouveau après avoir vérifié le projet actif.');
      setPrepared({ ...result, contextKey: expectedContext });
    } catch (error) { setError(message(error)); }
    finally { setWorking(''); }
  };

  const exportFile = async (format: string) => {
    if (currentExportBlocked || working) return;
    setWorking('Export de l’instantané enregistré…'); setError(''); setNotice('');
    try { await downloadPid(format); setNotice('Export P&ID téléchargé.'); }
    catch (error) { setError(message(error)); }
    finally { setWorking(''); }
  };

  const changeDrawing = (settings: PidDrawingSettings) => {
    setDrawingDraft(current => ({ ...current, settings, edited: JSON.stringify(settings) !== current.base }));
    setError(''); setNotice('');
  };
  const previewDrawing = async () => {
    if (working || drawingError || drawingMismatch || previewBlocked) return;
    const expectedContext = drawingDraft.contextKey;
    const settings = drawingDraft.settings;
    setWorking('Génération de l’aperçu local…'); setError('');
    try {
      const result = await api<PidDrawingPreview>('/pid/preview', 'POST', settings);
      if (contextRef.current !== expectedContext) throw new Error('Le contexte a changé pendant la génération. Votre mise en page reste conservée ; vérifiez le projet actif.');
      if (!/^data:image\/png;base64,/.test(result.image_data_url) || !Number.isFinite(result.width_mm) || !Number.isFinite(result.height_mm) || result.width_mm <= 0 || result.height_mm <= 0) throw new Error('Le service n’a pas fourni un aperçu PNG local valide.');
      setDrawingPreview({ result, settings: JSON.stringify(settings), contextKey: expectedContext, projectId: drawingDraft.projectId });
    } catch (error) { setError(message(error)); }
    finally { setWorking(''); }
  };
  const applyDrawing = () => {
    if (working || drawingError || drawingMismatch || drawingBlocked) return;
    try {
      onApplyDrawing(drawingDraft.settings, drawingDraft.contextKey, drawingDraft.projectId);
      setDrawingDraft(current => ({ ...current, base: JSON.stringify(current.settings), edited: false }));
      setNotice('Mise en page appliquée au brouillon du projet. Enregistrez le projet avant l’export.');
    } catch (error) { setError(message(error)); }
  };
  const saveDrawing = async () => {
    if (working || drawingError || drawingMismatch || drawingBlocked) return;
    setWorking('Enregistrement de la mise en page et du projet…'); setError('');
    try {
      const saved = await onSaveDrawing(drawingDraft.settings, drawingDraft.contextKey, drawingDraft.projectId);
      const settings = drawingDefaults(saved.settings);
      setDrawingDraft({ settings, base: JSON.stringify(settings), projectId: saved.projectId, contextKey: saved.contextKey, edited: false });
      setNotice('Mise en page et brouillon du projet enregistrés. Les exports utilisent ces réglages.');
    } catch (error) { setError(message(error)); }
    finally { setWorking(''); }
  };
  useEffect(() => {
    const saveShortcut = (event: KeyboardEvent) => {
      if (!open || tab !== 'drawing' || !drawingDraft.edited || !(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 's') return;
      event.preventDefault(); event.stopImmediatePropagation();
      if (working) return;
      if (drawingError || drawingBlocked || drawingMismatch) setError(drawingError || drawingBlocked || 'Le contexte a changé. Votre mise en page reste conservée.');
      else void saveDrawing();
    };
    window.addEventListener('keydown', saveShortcut, true);
    return () => window.removeEventListener('keydown', saveShortcut, true);
  }, [open, tab, drawingDraft.edited, drawingError, drawingBlocked, drawingMismatch, working, saveDrawing]);

  if (!open) return null;
  return <div className="modal-backdrop pid-exchange-backdrop">
    <section className="modal pid-exchange" role="dialog" aria-modal="true" aria-labelledby="pid-exchange-title">
      <div className="modal-heading"><div><span className="eyebrow">DOCUMENTS & SCHÉMAS</span><h2 id="pid-exchange-title">Échanges P&ID</h2></div><button className="icon-button" aria-label="Fermer les échanges P&ID" onClick={onClose}><X size={20} /></button></div>
      <p className="pid-intro">Importez un dessin, revoyez son interprétation et préparez un projet FAT. Le traitement reste sur ce poste, avec des outils gratuits.</p>
      <nav className="pid-exchange-nav" aria-label="Actions P&ID">
        <button className={tab === 'import' ? 'active' : ''} aria-pressed={tab === 'import'} onClick={() => setTab('import')}><Upload size={16} />Importer et revoir</button>
        <button className={tab === 'export' ? 'active' : ''} aria-pressed={tab === 'export'} onClick={() => setTab('export')}><ArrowDownToLine size={16} />Exporter le P&ID</button>
        <button className={tab === 'drawing' ? 'active' : ''} aria-pressed={tab === 'drawing'} onClick={() => setTab('drawing')}><LayoutTemplate size={16} />Mise en page</button>
        <button className={tab === 'catalog' ? 'active' : ''} aria-pressed={tab === 'catalog'} onClick={() => setTab('catalog')}><BookOpen size={16} />Catalogue public</button>
      </nav>
      {error && <div className="pid-message pid-error" role="alert"><CircleAlert size={18} /><p>{error}</p><button className="icon-button" aria-label="Fermer l’erreur P&ID" onClick={() => setError('')}><X size={16} /></button></div>}
      {working && <p className="pid-progress" role="status"><LoaderCircle size={17} className="spin" />{working}</p>}
      {notice && !working && <p className="pid-progress" role="status"><Check size={17} />{notice}</p>}
      {loading && <p className="small-muted">Lecture des formats disponibles sur ce poste…</p>}
      {!loading && !capabilities && <button className="button" onClick={() => setAttempt(value => value + 1)}>Réessayer le chargement</button>}

      {tab === 'import' && <div className="pid-import">
        {project.pid_document && <div className="pid-existing-source"><div><strong>Document source enregistré dans ce projet</strong><p>{project.pid_document.source_name || project.pid_document.title}. Sa réouverture laisse le schéma et les essais intacts.</p></div><button className="button" disabled={Boolean(working)} onClick={() => { setError(''); reviewDocument(project.pid_document!, true); }}>Revoir le document source du projet</button></div>}
        <div className="pid-upload-card"><div className="pid-step-title"><span>1</span><div><h3>Choisir un document</h3><p>L’inspection laisse le projet actif et ses essais intacts.</p></div></div>
          <div className="pid-file-fields"><label className="pid-file-label">Document P&ID<input type="file" accept=".pdf,.dwg,.dxf,.svg,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp,.json,.pid,.graphml,.csv,.tsv,.zip,.drawio,.xml" disabled={Boolean(working)} onChange={event => { setFile(event.target.files?.[0] ?? null); setError(''); }} /></label>
            <label>Pages à inspecter<input value={pages} disabled={Boolean(working)} onChange={event => setPages(event.target.value)} placeholder="Ex. 1, 3-5" aria-describedby="pid-pages-help" /></label></div>
          <div className="pid-upload-options"><label className="check-label"><input type="checkbox" checked={ocr} disabled={Boolean(working) || capabilities?.ocr_available === false} onChange={event => setOcr(event.target.checked)} />Utiliser l’OCR local pour les pages numérisées{capabilities?.ocr_available === false && <span>(indisponible sur ce poste)</span>}</label><button className="button primary" disabled={!file || !capabilities || Boolean(working)} onClick={() => void inspect()}><FileSearch size={16} />Inspecter le document</button></div>
          <p className="small-muted" id="pid-pages-help">{capabilities?.limits.upload_mb ?? 20} Mo au maximum. Sans sélection, seule la première page est inspectée. Sélection explicite de {capabilities?.limits.max_pages ?? 20} pages au maximum. La disponibilité de l’OCR et du DWG dépend des outils locaux indiqués ci-dessous.</p>
          {capabilities && <details className="pid-format-details"><summary>Formats d’import et outils disponibles</summary><ul>{capabilities.imports.map(item => <li key={item.format}><strong>{item.label}</strong><span className={item.available ? 'pid-available' : 'pid-unavailable'}>{item.available ? 'Disponible' : 'Indisponible sur ce poste'}</span><p>{item.detail}</p></li>)}</ul></details>}
        </div>

        {document && <>
          <div className="pid-source-heading"><div className="pid-step-title"><span>2</span><div><h3>Revoir l’interprétation</h3><p>{document.source_name || document.title} · {document.source_format.toUpperCase()} · {document.equipment.length} repères proposés</p></div></div><button className="button" disabled={Boolean(working)} onClick={() => { setDocument(null); setPrepared(null); setNotice(''); }}>Retirer le document</button></div>
          <div className="pid-message"><CircleAlert size={18} /><p>Les repères, types et liaisons sont des propositions à vérifier sur le dessin. Un trait ne démontre ni son sens physique, ni une adresse PLC. Paramètres, échelles analogiques et mapping restent à déclarer dans le projet.</p></div>
          {document.warnings.length > 0 && <details className="pid-warnings" open><summary>{document.warnings.length} avertissement(s) d’extraction</summary><ul>{document.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></details>}
          {document.pages.length > 0 && <section className="pid-source-preview" aria-label="Aperçu du document source"><div className="pid-preview-heading"><h4>Document source</h4><label>Page affichée<select value={pageIndex} onChange={event => setPageIndex(Number(event.target.value))}>{document.pages.map((page, index) => <option key={page.number} value={index}>Page {page.number}</option>)}</select></label></div>
            {sourcePage?.image_data_url.startsWith('data:image/png;base64,') || sourcePage?.image_data_url.startsWith('data:image/jpeg;base64,') ? <a className="pid-page-image" href={sourcePage.image_data_url} target="_blank" rel="noopener noreferrer" aria-label={`Ouvrir l’aperçu de la page ${sourcePage.number}`}><img src={sourcePage.image_data_url} alt={`Dessin source, page ${sourcePage.number}`} /></a> : <p className="small-muted">Aucun aperçu raster pour ce format. Vérifiez le document dans votre lecteur local.</p>}
            {sourcePage?.text && <details><summary>Texte extrait de la page {sourcePage.number}</summary><pre>{sourcePage.text}</pre></details>}
          </section>}
          <div className="pid-review-heading"><h4>Équipements à conserver <span>{selection.length} / {maxEquipment}</span></h4><div className="button-row"><button className="button compact-button" disabled={Boolean(working)} onClick={() => { setSelection(document.equipment.slice(0, maxEquipment).map(item => item.id)); invalidate(); }}>Sélectionner les {Math.min(document.equipment.length, maxEquipment)} premiers</button><button className="button compact-button" disabled={Boolean(working)} onClick={() => { setSelection([]); invalidate(); }}>Tout désélectionner</button></div></div>
          {document.equipment.length > maxEquipment && <p className="pid-blocked">Le banc accepte {maxEquipment} équipements par projet. Seuls les {maxEquipment} premiers sont présélectionnés ; choisissez les repères à conserver. Le document source garde aussi les objets exclus.</p>}
          <label className="pid-search">Rechercher un repère<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Nom, identifiant ou repère source" /></label>
          <div className="pid-table-scroll" tabIndex={0} aria-label="Table des équipements proposés"><table className="pid-review-table"><thead><tr><th scope="col">Conserver</th><th scope="col">Repère et origine</th><th scope="col">Type FAT à confirmer</th><th scope="col">Incertitude</th></tr></thead><tbody>{filteredEquipment.slice(0, 250).map(item => <tr key={item.id} className={selected.has(item.id) ? 'pid-row-selected' : ''}>
            <td><input type="checkbox" aria-label={`Conserver ${item.name}`} checked={selected.has(item.id)} disabled={Boolean(working) || (!selected.has(item.id) && selection.length >= maxEquipment)} onChange={event => { setSelection(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id)); invalidate(); }} /></td>
            <th scope="row"><strong>{item.name}</strong><small>{item.source_tag || item.id} · page {item.page}</small>{item.provenance && <small>{item.provenance}</small>}</th>
            <td><select aria-label={`Type FAT de ${item.name}`} value={types[item.id] ?? ''} disabled={Boolean(working)} onChange={event => { setTypes(current => ({ ...current, [item.id]: event.target.value })); invalidate(); }}><option value="">Choisir un type…</option><optgroup label="Modèles simulés">{models.map(kind => <option key={kind.type} value={kind.type}>{kind.label}</option>)}</optgroup><optgroup label="Symboles P&ID · non simulés">{symbols.map(symbol => <option key={symbol.id} value={`pid:${symbol.id}`}>{symbol.label}</option>)}</optgroup></select>{item.type === 'unknown' && <small>Type source inconnu · conservé comme symbole documentaire</small>}{item.source_kind && <small>Type source : {item.source_kind}</small>}</td>
            <td><span>{confidence(item.confidence)}</span><small>{item.review_required ? 'Revue requise' : 'À confirmer'}</small></td>
          </tr>)}</tbody></table>{!filteredEquipment.length && <p className="pid-empty">Aucun repère correspondant. Un dessin sans repère lisible peut être construit manuellement dans le P&ID.</p>}</div>
          {filteredEquipment.length > 250 && <p className="small-muted">250 repères affichés sur {filteredEquipment.length}. Affinez la recherche pour trouver les autres repères.</p>}

          <div className="pid-review-heading"><h4>Connexions entre les équipements sélectionnés <span>{keptConnections.length} / {maxConnections}</span></h4><div className="button-row"><button className="button compact-button" disabled={Boolean(working)} onClick={() => { setConnections(availableConnections.slice(0, maxConnections).map(item => item.id)); invalidate(); }}>Conserver les connexions proposées</button><button className="button compact-button" disabled={Boolean(working)} onClick={() => { setConnections([]); invalidate(); }}>Retirer les connexions</button></div></div>
          {portsToReview.length > 0 && <p className="pid-blocked" role="status">Piquages sans position connue dans les symboles choisis : {portsToReview.join(', ')}. Leurs identifiants seront conservés ; vérifiez et raccordez ces piquages dans l’éditeur.</p>}
          {availableConnections.length ? <div className="pid-table-scroll" tabIndex={0} aria-label="Table des connexions proposées"><table className="pid-review-table"><thead><tr><th scope="col">Conserver</th><th scope="col">Liaison</th><th scope="col">Interprétation</th></tr></thead><tbody>{availableConnections.map(item => <tr key={item.id}><td><input type="checkbox" aria-label={`Conserver la connexion ${item.id}`} checked={connections.includes(item.id)} disabled={Boolean(working)} onChange={event => { setConnections(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id)); invalidate(); }} /></td><th scope="row">{equipmentById.get(item.source)?.name ?? item.source}{item.source_port ? ` · ${item.source_port}` : ''} {item.directed ? '→' : '↔'} {equipmentById.get(item.target)?.name ?? item.target}{item.target_port ? ` · ${item.target_port}` : ''}<small>{item.label || item.id}</small></th><td>{item.inferred ? 'Liaison inférée' : 'Liaison déclarée'}<small>{item.directed ? 'Sens déclaré, à vérifier' : 'Sens non déclaré'} · {confidence(item.confidence)}</small></td></tr>)}</tbody></table></div> : <p className="pid-empty">Aucune connexion proposée pour cette sélection. Les liaisons restent à dessiner et vérifier dans le P&ID.</p>}
          <div className="pid-prepare-card"><div className="pid-step-title"><span>3</span><div><h3>Préparer un nouveau projet</h3><p>Le projet actuel reste enregistré. Le nouveau brouillon contient le schéma sélectionné, sans variable, scénario, mapping ni cible PLC.</p></div></div>
            {selection.some(id => ['heat_exchanger', 'valve_three_way'].includes(types[id])) && <p className="pid-model-choice-note">Vous avez choisi un modèle simulé. Ses paramètres utilisent les valeurs du catalogue ; renseignez les conditions thermiques ou les trois cuves avant de démarrer. Le dessin source ne fournit pas ces paramètres.</p>}
            <label>Nom du nouveau projet<input value={name} maxLength={120} disabled={Boolean(working)} onChange={event => { setName(event.target.value); invalidate(); }} /></label>
            <label className="check-label"><input type="checkbox" checked={reviewed} disabled={Boolean(working)} onChange={event => { setReviewed(event.target.checked); setPrepared(null); setConfirmed(false); }} />J’ai vérifié les équipements sélectionnés, leurs types et les connexions conservées.</label>
            {cannotPrepare && <p className="pid-blocked" id="pid-prepare-blocked">{cannotPrepare}</p>}
            <button className="button primary" disabled={Boolean(cannotPrepare || working)} aria-describedby={cannotPrepare ? 'pid-prepare-blocked' : undefined} onClick={() => void prepare()}><FileSearch size={16} />Préparer le brouillon P&ID</button>
            {preparedCurrent && <div className="pid-prepared" aria-label="Brouillon P&ID préparé"><h4>{preparedCurrent.project.name}</h4><p>{preparedCurrent.project.equipment.length} équipements · {preparedCurrent.project.connections.length} connexions · mode démonstration local</p>{preparedCurrent.warnings.length > 0 && <ul>{preparedCurrent.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>}
              <label className="check-label"><input type="checkbox" checked={confirmed} disabled={Boolean(working || applyBlocked)} onChange={event => setConfirmed(event.target.checked)} />Afficher ce nouveau projet dans l’éditeur. Je l’enregistrerai avec « Enregistrer ».</label>
              <button className="button primary" disabled={!confirmed || Boolean(working || applyBlocked)} onClick={() => { try { onApply(preparedCurrent.project, preparedCurrent.contextKey); setPrepared(null); setConfirmed(false); } catch (error) { setError(message(error)); } }}>Appliquer au brouillon</button>
            </div>}
          </div>
        </>}
      </div>}

      {tab === 'export' && <div className="pid-export"><h3>Exporter « {project.name} »</h3><p>Chaque fichier représente le P&ID du projet enregistré. Les formats de dessin conservent la présentation et les repères ; le JSON P&ID conserve aussi le document d’échange.</p><p className="small-muted">Pour conserver variables, scénarios et historique, utilisez l’archive FAT dans « Ouvrir ».</p>
        {currentExportBlocked && <p className="pid-message" role="status">{currentExportBlocked}</p>}
        <div className="pid-export-grid">{capabilities?.exports.map(item => <article className="pid-format-card" key={item.format}><div><h4>{item.label}</h4><span className={item.available ? 'pid-available' : 'pid-unavailable'}>{item.available ? 'Disponible localement' : 'Indisponible sur ce poste'}</span></div><p>{item.detail}</p><button className="button" disabled={!item.available || Boolean(currentExportBlocked || working)} onClick={() => void exportFile(item.format)}><ArrowDownToLine size={15} />Télécharger {item.format.toUpperCase()}</button></article>)}</div>
        <aside className="pid-cad-fonts"><h4>Polices des fichiers CAO</h4><p>Le PDF incorpore ses polices. Les DXF et DWG utilisent Geist : transmettez les fichiers de police avec le dessin pour conserver les mêmes métriques dans votre logiciel CAO.</p><a className="button" href="/api/pid/cad-fonts" download="vanguard-pid-cad-fonts.zip"><ArrowDownToLine size={15} />Télécharger les polices CAO et leur licence</a></aside>
      </div>}

      {tab === 'drawing' && <PidDrawingEditor settings={drawingDraft.settings} projectName={project.name} busy={Boolean(working)} dirty={drawingDraft.edited} mismatch={drawingMismatch} validation={drawingError} actionBlocked={drawingBlocked} previewBlocked={previewBlocked} preview={drawingPreview?.result ?? null} previewStale={Boolean(drawingPreview && (drawingPreview.settings !== JSON.stringify(drawingDraft.settings) || drawingPreview.contextKey !== contextKey || drawingPreview.projectId !== project.id))} onChange={changeDrawing} onPreview={() => void previewDrawing()} onApply={applyDrawing} onSave={() => void saveDrawing()} onDownload={() => downloadText(JSON.stringify({ project_id: drawingDraft.projectId, pid_drawing: drawingDraft.settings }, null, 2) + '\n', `${drawingDraft.projectId}-mise-en-page-brouillon.json`)} onReload={() => { const settings = drawingDefaults(project.pid_drawing); setDrawingDraft({ settings, base: JSON.stringify(settings), projectId: project.id, contextKey, edited: false }); setDrawingPreview(null); setError(''); setNotice('Réglages du projet repris explicitement.'); }} />}

      {tab === 'catalog' && <div className="pid-public-catalog"><h3>Documents et jeux de données publics</h3><p>Catalogue constitué à partir du travail de Scott Duncan / ScottDuncanAI. Les liens ouvrent les sources externes. Téléchargez les documents voulus, vérifiez leurs droits d’usage, puis inspectez-les ici.</p>
        <PidConventionsGuide />
        {sources && <><p className="pid-source-credit"><a href={safeLink(sources.source.url)} target="_blank" rel="noopener noreferrer">{sources.source.name}<ExternalLink size={13} /></a><span>{sources.source.license} · révision {sources.source.revision}</span></p>{sources.source.changes && <p className="small-muted">{sources.source.changes}</p>}<p className="small-muted">Les documents référencés ne sont pas redistribués par Vanguard FAT Studio. Leurs licences peuvent différer de celle du catalogue. Aucun téléchargement automatique n’est effectué.</p>{sources.notice && <p className="small-muted">{sources.notice}</p>}
          <div className="pid-catalog-list">{sources.entries.map(entry => <article key={entry.id}><span className="pid-category">{entry.category === 'pid' ? 'P&ID' : 'Séries temporelles'}</span><h4>{entry.title}</h4><p>{entry.description}</p>{entry.pages && <p className="small-muted">Pages / fichiers référencés : {Array.isArray(entry.pages) ? entry.pages.join(', ') : entry.pages}</p>}<p className="pid-license">{entry.license_note}</p><a className="button" href={safeLink(entry.url)} target="_blank" rel="noopener noreferrer">Ouvrir la source<ExternalLink size={14} /></a></article>)}</div>
        </>}
      </div>}
      <div className="pid-exchange-footer"><span>Votre revue reste disponible tant que cet onglet du navigateur reste ouvert.</span><button className="button" onClick={onClose}>Fermer</button></div>
    </section>
  </div>;
}
