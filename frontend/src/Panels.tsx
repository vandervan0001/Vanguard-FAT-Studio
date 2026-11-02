import { useEffect, useMemo, useRef, useState } from 'react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ArrowDownToLine, ArrowLeftRight, Check, CircleAlert, Clock3, FileJson, FileText, Flag, FolderClock, Info, ListChecks, Plus, Search, ShieldCheck, Trash2, Upload, Wifi, X } from 'lucide-react';
import { api, download, downloadText } from './api';
import { useModalKeyboard } from './useModalKeyboard';
import { parseScenarioSteps } from './scenarioFormat';
import { ForceField } from './PidCanvas';
import { fmt, uid, type CatalogItem, type Project, type ReportDraft, type RunResult, type Snapshot, type Tag, type Scenario, type ScenarioDraft, type RunSummary, type Validation } from './types';

type CommonProps = {
  project: Project; state: Snapshot | null; locked: boolean; online: boolean;
  onChange: (update: (project: Project) => Project) => void;
  onError: (message: string) => void; onSnapshot: (state: Snapshot) => void;
};

export function VariablesPanel({ project, state, locked, online, onChange, onError, onSnapshot, onImport, onExport }: CommonProps & { onImport: (csv: string) => Promise<void>; onExport: () => Promise<void> }) {
  const [search, setSearch] = useState('');
  const [direction, setDirection] = useState('all');
  const [expanded, setExpanded] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const tags = project.tags.filter(tag => (direction === 'all' || tag.direction === direction) && `${tag.name} ${tag.id} ${tag.node_id}`.toLowerCase().includes(search.toLowerCase()));
  const update = (id: string, patch: Partial<Tag>) => onChange(project => ({ ...project, tags: project.tags.map(tag => tag.id === id ? { ...tag, ...patch } : tag) }));
  const addTag = () => {
    const id = uid('tag');
    onChange(project => ({ ...project, tags: [...project.tags, { id, name: `Tag_${project.tags.length + 1}`, direction: 'input', data_type: 'REAL', unit: '%', initial_value: 0, min: 0, max: 100, node_id: '', writable: true }] }));
    setExpanded(id);
  };
  const removeTag = (tag: Tag) => {
    if (!window.confirm(`Supprimer ${tag.name} ? Les associations à cette variable seront retirées. Vérifiez ensuite les scénarios.`)) return;
    onChange(project => ({ ...project, tags: project.tags.filter(entry => entry.id !== tag.id), equipment: project.equipment.map(equipment => ({ ...equipment, bindings: Object.fromEntries(Object.entries(equipment.bindings).filter(([, id]) => id !== tag.id)) })) }));
  };
  return <section className="page-panel">
    <div className="section-heading"><div><div className="eyebrow">INTERFACE D’ÉCHANGE</div><h2>Variables & mapping PLC</h2><p>Déclarez les variables autorisées et associez-les aux équipements du P&ID.</p></div>
      <div className="button-row"><button className="button" disabled={!online} onClick={() => void onExport()}><ArrowDownToLine size={16} />Exporter CSV</button><button className="button" disabled={locked} onClick={() => input.current?.click()}><Upload size={16} />Importer CSV</button><button className="button primary" disabled={locked || project.tags.length >= 200} onClick={addTag}><Plus size={16} />Nouvelle variable</button></div>
    </div>
    <input ref={input} type="file" accept=".csv,text/csv" hidden onChange={event => { const file = event.target.files?.[0]; if (file && file.size > 2_000_000) onError('Le fichier CSV dépasse 2 Mo.'); else if (file) void file.text().then(onImport).catch(error => onError(String(error))); event.target.value = ''; }} />
    <div className="information-strip"><ArrowLeftRight size={19} /><div><strong>Entrée PLC</strong> : mesure simulée écrite vers le programme. <strong>Sortie PLC</strong> : commande lue depuis le programme. Le banc ne force jamais une sortie PLC.</div></div>
    <div className="table-toolbar"><div className="search-field"><Search size={16} /><input aria-label="Rechercher une variable" placeholder="Rechercher un tag, un NodeId…" value={search} onChange={event => setSearch(event.target.value)} /></div>
      <div className="segmented">{[['all', 'Toutes'], ['input', 'Entrées PLC'], ['output', 'Sorties PLC']].map(([key, name]) => <button key={key} className={direction === key ? 'active' : ''} onClick={() => setDirection(key)}>{name}</button>)}</div><span className="small-muted">{tags.length} / {project.tags.length} variables</span></div>
    <div className="table-container"><table className="tags-table"><thead><tr><th>Variable</th><th>Sens</th><th>Type</th><th>Valeur</th><th>Qualité</th><th>Unité</th><th>Association OPC UA</th><th></th></tr></thead>
      <tbody>{tags.flatMap(tag => {
        const live = state?.tags[tag.id];
        const boundTo = project.equipment.filter(equipment => Object.values(equipment.bindings).includes(tag.id)).map(equipment => equipment.name);
        return [<tr key={tag.id} className={live?.forced ? 'row-forced' : ''}>
          <td><button className="tag-name" onClick={() => setExpanded(expanded === tag.id ? null : tag.id)}>{tag.name}<small>{boundTo.length ? boundTo.join(', ') : 'Non associé'}</small></button></td>
          <td><span className={`direction-pill ${tag.direction}`}>{tag.direction === 'input' ? '→ Entrée' : '← Sortie'}</span></td>
          <td className="mono muted">{tag.data_type}</td><td><strong className="mono">{fmt(live?.value ?? tag.initial_value)}</strong>{live?.forced && <span className="inline-forced">F</span>}</td>
          <td><span className={`quality-value ${live?.quality && /bad|stale|error|disconnected/i.test(live.quality) ? 'bad' : ''}`}><span />{live?.quality ?? 'Initial'}</span></td>
          <td>{tag.unit || '—'}</td><td className="mono node-id">{tag.node_id || <span className="small-muted">Non défini · démo</span>}</td><td><button className="icon-button" title="Éditer la variable" onClick={() => setExpanded(expanded === tag.id ? null : tag.id)}>{expanded === tag.id ? <X size={16} /> : <ArrowLeftRight size={16} />}</button></td>
        </tr>, ...(expanded === tag.id ? [<tr key={`${tag.id}-details`} className="tag-details"><td colSpan={8}><div className="tag-detail-grid">
          <label>Nom<input disabled={locked} value={tag.name} onChange={event => update(tag.id, { name: event.target.value })} /></label>
          <label>Sens<select disabled={locked} value={tag.direction} onChange={event => update(tag.id, { direction: event.target.value as Tag['direction'], writable: event.target.value === 'input' })}><option value="input">Entrée simulée → PLC</option><option value="output">Commande PLC → modèle</option></select></label>
          <label>Type<select disabled={locked} value={tag.data_type} onChange={event => { const data_type = event.target.value as Tag['data_type']; update(tag.id, { data_type, initial_value: data_type === 'BOOL' ? false : 0, min: data_type === 'BOOL' ? null : 0, max: data_type === 'BOOL' ? null : data_type === 'INT' ? 32767 : data_type === 'DINT' ? 2147483647 : 100 }); }}>{['BOOL', 'INT', 'DINT', 'REAL'].map(type => <option key={type}>{type}</option>)}</select></label>
          <label>Unité<input disabled={locked} value={tag.unit} onChange={event => update(tag.id, { unit: event.target.value })} /></label>
          <label>Valeur initiale{tag.data_type === 'BOOL' ? <select disabled={locked} value={String(tag.initial_value)} onChange={event => update(tag.id, { initial_value: event.target.value === 'true' })}><option value="false">FALSE</option><option value="true">TRUE</option></select> : <input disabled={locked} type="number" step={tag.data_type === 'REAL' ? 'any' : 1} value={Number(tag.initial_value)} onChange={event => update(tag.id, { initial_value: Number(event.target.value) })} />}</label>
          <label>Minimum<input disabled={locked || tag.data_type === 'BOOL'} type="number" step="any" value={tag.min ?? ''} placeholder="Sans limite" onChange={event => update(tag.id, { min: event.target.value === '' ? null : Number(event.target.value) })} /></label>
          <label>Maximum<input disabled={locked || tag.data_type === 'BOOL'} type="number" step="any" value={tag.max ?? ''} placeholder="Sans limite" onChange={event => update(tag.id, { max: event.target.value === '' ? null : Number(event.target.value) })} /></label>
          <label className="span-2">NodeId OPC UA<input className="mono" disabled={locked} value={tag.node_id} placeholder={'ns=3;s="DB_FAT"."Level"'} onChange={event => update(tag.id, { node_id: event.target.value })} /></label>
          <label className="check-label"><input disabled={locked || tag.direction === 'output'} type="checkbox" checked={tag.writable} onChange={event => update(tag.id, { writable: event.target.checked })} />Écriture explicitement autorisée</label>
          <div className="tag-action-cell">{tag.direction === 'input' && state?.run_id ? <><span>Forçage de test</span><ForceField tag={tag} state={state} disabled={!online} onSnapshot={onSnapshot} onError={onError} /></> : <span className="small-muted">{tag.direction === 'output' ? 'Variable en lecture seule.' : 'Démarrez un essai pour forcer la mesure.'}</span>}</div>
          <div className="tag-delete-cell"><span className="mono small-muted">{tag.id}</span><button disabled={locked} className="danger-text" onClick={() => removeTag(tag)}><Trash2 size={14} />Supprimer</button></div>
        </div></td></tr>] : [])];
      })}</tbody></table>
      {!tags.length && <div className="empty-state"><ArrowLeftRight size={28} /><h3>{project.tags.length ? 'Aucun résultat' : 'Aucune variable définie'}</h3><p>{project.tags.length ? 'Essayez un autre terme de recherche.' : 'Créez vos variables ici, ou utilisez « Créer les tags manquants » dans les propriétés d’un équipement.'}</p></div>}
    </div>
  </section>;
}

export function ScenariosPanel({ project, state, locked, onChange, selectedId, onSelect, onDraftChange }: CommonProps & { selectedId: string; onSelect: (id: string) => void; onDraftChange: (draft: ScenarioDraft | null) => void }) {
  const selected = project.scenarios.find(scenario => scenario.id === selectedId) ?? null;
  const [stepsText, setStepsText] = useState('[]');
  const [jsonError, setJsonError] = useState('');
  const [pending, setPending] = useState(false);
  useEffect(() => { setStepsText(JSON.stringify(selected?.steps ?? [], null, 2)); setJsonError(''); setPending(false); onDraftChange(null); }, [selected?.id]); // reset only when choosing a different scenario
  const update = (patch: Partial<Scenario>) => { if (selected) onChange(project => ({ ...project, scenarios: project.scenarios.map(scenario => scenario.id === selected.id ? { ...scenario, ...patch } : scenario) })); };
  const add = () => {
    if (pending && !window.confirm('Abandonner les étapes non appliquées ?')) return;
    const id = uid('scenario');
    onChange(project => ({ ...project, scenarios: [...project.scenarios, { id, name: `Essai ${project.scenarios.length + 1}`, description: '', duration_s: 60, steps: [{ at_s: 0, action: 'marker', message: 'Début de l’essai' }] }] }));
    onSelect(id);
  };
  const applySteps = () => {
    try {
      const steps = parseScenarioSteps(stepsText, selected?.duration_s ?? 0);
      update({ steps }); setPending(false); onDraftChange(null); setJsonError('');
    } catch (error) { setJsonError(error instanceof Error ? error.message : String(error)); }
  };
  const choose = (id: string) => { if (!pending || window.confirm('Abandonner les étapes non appliquées ?')) onSelect(id); };
  return <section className="page-panel scenarios-page">
    <div className="section-heading"><div><div className="eyebrow">ESSAIS REPRODUCTIBLES</div><h2>Scénarios de FAT</h2><p>Enchaînez les actions, injectez les défauts et vérifiez les réactions attendues.</p></div><button className="button primary" disabled={locked} onClick={add}><Plus size={16} />Nouveau scénario</button></div>
    <div className="scenario-layout"><aside className="scenario-list"><button className={`scenario-list-item ${!selectedId ? 'active' : ''}`} onClick={() => choose('')}><span className="scenario-icon"><Clock3 size={18} /></span><span><strong>Essai libre</strong><small>Sans séquence automatique</small></span></button>
      {project.scenarios.map(scenario => <button key={scenario.id} className={`scenario-list-item ${selectedId === scenario.id ? 'active' : ''}`} onClick={() => choose(scenario.id)}><span className="scenario-icon"><ListChecks size={18} /></span><span><strong>{scenario.name}</strong><small>{scenario.steps.length} étapes · {fmt(scenario.duration_s)} s</small></span></button>)}
    </aside>
    <div className="scenario-detail">{selected ? <>
      <div className="scenario-title-row"><label>Nom du scénario<input disabled={locked} value={selected.name} onChange={event => update({ name: event.target.value })} /></label><label className="duration-input">Durée (s)<input disabled={locked} type="number" min={.1} step="any" value={selected.duration_s} onChange={event => update({ duration_s: Number(event.target.value) })} /></label><button className="icon-button danger-text" title="Supprimer le scénario" disabled={locked} onClick={() => { if (window.confirm(`Supprimer le scénario « ${selected.name} » ?`)) { onChange(project => ({ ...project, scenarios: project.scenarios.filter(scenario => scenario.id !== selected.id) })); onSelect(''); } }}><Trash2 size={18} /></button></div>
      <label>Description<textarea disabled={locked} rows={2} value={selected.description} onChange={event => update({ description: event.target.value })} placeholder="Objectif, conditions initiales et résultat attendu" /></label>
      <div className="timeline">{selected.steps.map((step, index) => <div className={`timeline-step ${state?.scenario.id === selected.id && index < state.scenario.completed_steps ? 'done' : ''}`} key={`${index}-${step.at_s}`}><span className="timeline-time">{fmt(step.at_s)} s</span><span className="timeline-dot" /><div><strong>{({ force: 'Forcer une entrée', release: 'Libérer le forçage', fault: 'Injecter un défaut', clear_fault: 'Lever un défaut', marker: 'Marqueur', expect: 'Vérification' })[step.action]}</strong><p>{step.message || `${step.target ?? ''}${step.value !== undefined ? ' → ' + JSON.stringify(step.value) : ''}`}</p></div></div>)}</div>
      <div className="editor-title"><h3>Étapes du scénario <span className="type-label">JSON</span></h3><span className="small-muted">Les temps sont exprimés en secondes simulées.</span></div>
      <textarea className="code-editor" disabled={locked} spellCheck={false} aria-label="Étapes JSON du scénario" rows={14} value={stepsText} onChange={event => { setStepsText(event.target.value); setPending(true); onDraftChange({ scenarioId: selected.id, text: event.target.value }); setJsonError(''); }} />
      {jsonError && <div className="inline-error"><CircleAlert size={16} />{jsonError}</div>}
      <div className="scenario-editor-actions"><span className={pending ? 'unsaved-text' : 'small-muted'}>{pending ? 'Étapes modifiées : appliquez-les avant de sauvegarder ou démarrer.' : 'Étapes appliquées au projet.'}</span><div className="button-row">{pending && <button className="button" onClick={() => downloadText(stepsText, `${selected.id}-etapes-brouillon.json`)}><ArrowDownToLine size={16} />Télécharger les étapes JSON</button>}<button className="button" disabled={locked || !pending} onClick={applySteps}><Check size={16} />Appliquer les étapes</button></div></div>
      <details className="help-details"><summary>Syntaxe des actions et exemples</summary><p><code>target</code> désigne l’identifiant interne d’un tag, ou d’un équipement pour les défauts.</p><pre>{JSON.stringify([
        { at_s: 5, action: 'marker', message: 'Contrôle de la montée en niveau' },
        { at_s: 10, action: 'force', target: project.tags.find(tag => tag.direction === 'input')?.id ?? 'tag_id', value: 85 },
        { at_s: 12, action: 'expect', target: project.tags.find(tag => tag.direction === 'output')?.id ?? 'command_id', operator: 'eq', value: false, tolerance: 0, message: 'Arrêt attendu' },
        { at_s: 15, action: 'release', target: project.tags.find(tag => tag.direction === 'input')?.id ?? 'tag_id' },
        { at_s: 20, action: 'fault', target: project.equipment.find(equipment => equipment.type === 'pump')?.id ?? 'pump_id', value: { kind: 'motor_trip' } },
        { at_s: 30, action: 'clear_fault', target: project.equipment.find(equipment => equipment.type === 'pump')?.id ?? 'pump_id' },
      ], null, 2)}</pre><p>Opérateurs d’assertion : <code>eq, ne, gt, ge, lt, le</code>. Le moteur vérifie les types, les bornes et les références au démarrage.</p></details>
      {state?.scenario.id === selected.id && state.scenario.assertions.length > 0 && <div className="assertion-results"><h3>Résultats des vérifications</h3>{state.scenario.assertions.map((assertion, index) => <pre key={index}>{JSON.stringify(assertion, null, 2)}</pre>)}</div>}
    </> : <div className="empty-state scenario-free"><Clock3 size={35} /><h3>Essai libre</h3><p>Le procédé évolue jusqu’à votre arrêt. Utilisez le P&ID pour forcer une mesure ou injecter un défaut, et le journal pour consigner vos observations.</p><button className="button" disabled={locked} onClick={add}><Plus size={16} />Créer une séquence</button></div>}</div></div>
    <div className="information-strip"><Info size={18} /><div>Le scénario s’arrête en pause à la fin de sa durée. Pour le rejouer avec les mêmes conditions initiales, arrêtez l’essai puis réinitialisez le modèle. {project.plc.mode === 'opcua' && 'Les états internes du PLC doivent être remis à leur état initial dans TIA par l’ingénieur.'}</div></div>
  </section>;
}

const CHART_COLORS = ['#098f7e', '#d98236', '#5478bc', '#9b5cb4', '#ad6969', '#4a9dac', '#657640', '#b25783'];
export function TrendChart({ project, state, compact = false }: { project: Project; state: Snapshot | null; compact?: boolean }) {
  const numericTagIds = project.tags.filter(tag => tag.data_type !== 'BOOL').map(tag => tag.id).join('|');
  const defaults = useMemo(() => numericTagIds ? numericTagIds.split('|').slice(0, compact ? 3 : 5) : [], [numericTagIds, compact]);
  const [selected, setSelected] = useState(defaults);
  useEffect(() => setSelected(defaults), [defaults]);
  const data = useMemo(() => (state?.series ?? []).map(point => ({ time_s: point.time_s, ...Object.fromEntries(Object.entries(point.values).map(([key, value]) => [key, typeof value === 'boolean' ? Number(value) : value])) })), [state?.series]);
  return <div className={`trend-component ${compact ? 'compact-trend' : ''}`}>
    {!compact && <div className="trend-tag-picker">{project.tags.map(tag => <label key={tag.id}><input type="checkbox" checked={selected.includes(tag.id)} disabled={!selected.includes(tag.id) && selected.length >= 8} onChange={event => setSelected(current => event.target.checked ? [...current, tag.id] : current.filter(id => id !== tag.id))} /><span style={{ background: selected.includes(tag.id) ? CHART_COLORS[selected.indexOf(tag.id) % CHART_COLORS.length] : '#b9c9cf' }} />{tag.name}{tag.unit && <small>{tag.unit}</small>}</label>)}</div>}
    <div className="chart-container" style={{ height: compact ? 180 : 340 }}><ResponsiveContainer width="100%" height="100%" minWidth={0}>
      <LineChart data={data} margin={{ top: 15, right: 25, left: compact ? -20 : 5, bottom: 2 }}>
        <CartesianGrid strokeDasharray="3 4" vertical={false} stroke="#e7ecef" /><XAxis dataKey="time_s" type="number" domain={['dataMin', 'dataMax']} tick={{ fontSize: 11, fill: '#71818e' }} tickLine={false} axisLine={false} tickFormatter={value => `${Number(value).toFixed(0)} s`} /><YAxis tick={{ fontSize: 11, fill: '#71818e' }} tickLine={false} axisLine={false} width={50} />
        <Tooltip labelFormatter={value => `Temps simulé : ${fmt(value)} s`} contentStyle={{ border: '1px solid #dce4e9', borderRadius: 7, fontSize: 12 }} formatter={(value: unknown, name: unknown) => [fmt(value, 3), String(name)]} />
        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 7 }} iconType="plainline" />
        {selected.filter(id => project.tags.some(tag => tag.id === id)).map(id => {
          const tag = project.tags.find(tag => tag.id === id)!;
          return <Line key={id} type="linear" dataKey={id} name={`${tag.name}${tag.unit ? ' (' + tag.unit + ')' : ''}`} stroke={CHART_COLORS[selected.indexOf(tag.id) % CHART_COLORS.length]} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} />;
        })}
      </LineChart>
    </ResponsiveContainer>{!data.length && <div className="chart-no-data">Les courbes apparaîtront au démarrage de l’essai.</div>}</div>
  </div>;
}

export function TrendsPanel({ project, state, online, onError, onSnapshot, draft, onDraftChange }: Pick<CommonProps, 'project' | 'state' | 'online' | 'onError' | 'onSnapshot'> & { draft: ReportDraft; onDraftChange: (update: (draft: ReportDraft) => ReportDraft) => void }) {
  const { marker, verdict, comment } = draft;
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [showRuns, setShowRuns] = useState(false);
  const [busy, setBusy] = useState(false);
  const wrongRun = draft.runId !== (state?.run_id ?? null);
  useModalKeyboard(showRuns, () => setShowRuns(false));
  const mutate = async (path: string, body: unknown) => {
    if (!online || busy || wrongRun || !draft.runId) return false;
    setBusy(true);
    try { onSnapshot(await api<Snapshot>(path, 'POST', body, undefined, draft.runId)); return true; }
    catch (error) { onError(error instanceof Error ? error.message : String(error)); return false; }
    finally { setBusy(false); }
  };
  const saveResult = async () => {
    const submitted = draft;
    if (await mutate('/result', { verdict, comment })) onDraftChange(current => current.runId === submitted.runId && current.verdict === submitted.verdict && current.comment === submitted.comment ? { ...current, resultDirty: false, saved: true } : current);
  };
  const addMarker = async () => {
    const submitted = draft;
    if (await mutate('/markers', { message: marker })) onDraftChange(current => current.runId === submitted.runId && current.marker === submitted.marker ? { ...current, marker: '' } : current);
  };
  const loadRuns = async () => { try { setRuns(await api<RunSummary[]>('/runs')); setShowRuns(true); } catch (error) { onError(String(error)); } };
  return <section className="page-panel">
    {wrongRun && <div className="information-strip" role="alert"><CircleAlert size={18} /><div>Ce brouillon appartient à l’essai précédent. Il est conservé ici ; il ne peut pas être envoyé à l’essai actuel.<div className="button-row"><button className="button compact-button" onClick={() => downloadText(JSON.stringify({ run_id: draft.runId, verdict, comment, marker }, null, 2) + '\n', `${draft.runId ?? 'sans-essai'}-brouillon-rapport.json`)}>Télécharger le brouillon du rapport</button><button className="button compact-button" onClick={() => { if (window.confirm('Abandonner ce brouillon et afficher la conclusion de l’essai actuel ?')) onDraftChange(() => ({ runId: state?.run_id ?? null, verdict: state?.result?.verdict ?? 'not_evaluated', comment: state?.result?.comment ?? '', marker: '', resultDirty: false, saved: false })); }}>Afficher l’essai actuel</button></div></div></div>}
    <div className="section-heading"><div><div className="eyebrow">TRACES & RÉSULTATS</div><h2>Tendances et rapport d’essai</h2><p>Chaque valeur, défaut et intervention est lié au temps de simulation et à l’essai.</p></div><div className="button-row"><button className="button" disabled={!online} onClick={() => void loadRuns()}><FolderClock size={16} />Historique</button><button className="button" disabled={!online || !state?.run_id} onClick={() => download(`/runs/${encodeURIComponent(state!.run_id!)}/csv`)}><ArrowDownToLine size={16} />Données CSV</button><button className="button primary" disabled={!online || !state?.run_id} onClick={() => download(`/runs/${encodeURIComponent(state!.run_id!)}/report`)}><FileText size={16} />Rapport FAT</button></div></div>
    <div className="chart-panel"><div className="chart-heading"><h3>Évolution du procédé</h3><span className="live-label"><span className={state?.status === 'running' ? 'live-dot' : ''} />{state?.status === 'running' ? 'Acquisition en cours' : 'Dernières valeurs acquises'}</span></div><TrendChart project={project} state={state} /><p className="chart-note">Jusqu’à 8 variables dans leurs unités natives. Les BOOL valent 0 / 1. Fenêtre glissante ; l’export contient l’historique complet.</p></div>
    <div className="evidence-grid"><div className="journal-panel"><div className="chart-heading"><h3>Journal de l’essai</h3><span className="small-muted">{state?.events.length ?? 0} événements visibles</span></div><form className="marker-form" onSubmit={event => { event.preventDefault(); void addMarker(); }}><Flag size={17} /><input aria-label="Commentaire de l’essai" value={marker} onChange={event => { const marker = event.target.value; onDraftChange(current => ({ ...current, marker })); }} placeholder="Ajouter un marqueur ou une observation…" maxLength={2000} /><button className="button compact-button" disabled={!online || !state?.run_id || wrongRun || !marker.trim() || busy}>Ajouter</button></form><div className="event-list">{[...(state?.events ?? [])].reverse().map(event => <div className={`event-row ${event.kind}`} key={event.id}><span className="event-time">{fmt(event.sim_time_s)} s<small>{new Date(event.timestamp).toLocaleTimeString('fr-CH')}</small></span><span className="event-kind">{event.kind}</span><p>{event.message}</p></div>)}{!state?.events.length && <p className="empty-inline">Les actions et diagnostics apparaîtront ici.</p>}</div></div>
      <div className="verdict-panel"><h3>Conclusion de l’ingénieur</h3><p>Les assertions automatiques complètent votre évaluation. La conclusion est enregistrée dans le rapport.</p><label>Résultat<select value={verdict} onChange={event => { const verdict = event.target.value as RunResult['verdict']; onDraftChange(current => ({ ...current, verdict, resultDirty: true, saved: false })); }}><option value="not_evaluated">Non évalué</option><option value="pass">Conforme</option><option value="fail">Non conforme</option></select></label><label>Observations<textarea rows={5} value={comment} maxLength={10000} onChange={event => { const comment = event.target.value; onDraftChange(current => ({ ...current, comment, resultDirty: true, saved: false })); }} placeholder="Écarts, réserves, conditions de l’essai…" /></label><button className="button primary full-width" disabled={!online || !state?.run_id || wrongRun || busy} onClick={() => void saveResult()}><Check size={16} />Enregistrer la conclusion</button>{draft.saved && <p className="success-text"><Check size={14} />Conclusion enregistrée</p>}{draft.resultDirty && <p className="unsaved-text">Conclusion modifiée, non enregistrée.</p>}<button className="text-link" disabled={!online || !state?.run_id} onClick={() => download(`/runs/${encodeURIComponent(state!.run_id!)}/json`)}><FileJson size={15} />Exporter les preuves JSON</button></div></div>
    {showRuns && <div className="modal-backdrop"><section className="modal wide-modal" role="dialog" aria-modal="true" aria-labelledby="runs-title"><div className="modal-heading"><h2 id="runs-title">Essais enregistrés</h2><button className="icon-button" onClick={() => setShowRuns(false)} aria-label="Fermer l’historique"><X size={18} /></button></div><div className="run-list">{runs.map(run => { const id = run.id ?? run.run_id ?? ''; return <div className="saved-run" key={id}><div><strong>{run.project_name ?? id}</strong><small>{run.started_at ? new Date(run.started_at).toLocaleString('fr-CH') : id}</small><span>{run.verdict ?? run.status ?? ''}</span></div><div className="button-row"><button className="button compact-button" onClick={() => download(`/runs/${encodeURIComponent(id)}/csv`)}>CSV</button><button className="button compact-button" onClick={() => download(`/runs/${encodeURIComponent(id)}/report`)}>Rapport</button><button className="button compact-button" onClick={() => download(`/runs/${encodeURIComponent(id)}/json`)}>JSON</button></div></div>; })}{!runs.length && <div className="empty-inline">Aucun essai enregistré.</div>}</div></section></div>}
  </section>;
}

export function ConnectionPanel({ project, state, locked, onChange, validation, onValidate, catalog }: CommonProps & { validation: Validation | null; onValidate: () => Promise<void>; catalog: CatalogItem[] }) {
  const plc = project.plc;
  const update = (patch: Partial<Project['plc']>) => onChange(project => ({ ...project, plc: { ...project.plc, ...patch } }));
  return <section className="page-panel connection-page">
    <div className="section-heading"><div><div className="eyebrow">CONFIGURATION DU BANC</div><h2>Connexion et modèle</h2><p>Un seul programme de contrôle, une seule cible virtuelle explicitement approuvée.</p></div><button className="button primary" disabled={locked} onClick={() => void onValidate()}><ShieldCheck size={16} />Valider le projet</button></div>
    <div className="connection-grid"><div className="connection-settings"><h3>Source des commandes PLC</h3><div className="mode-options"><button className={`mode-option ${plc.mode === 'demo' ? 'active' : ''}`} disabled={locked} onClick={() => update({ mode: 'demo' })}><span className="radio-mark" /><div><strong>Démonstration locale</strong><p>Contrôleur de démonstration intégré. Fonctionne sans Siemens.</p></div><span className="badge neutral">DÉMO</span></button><button className={`mode-option ${plc.mode === 'opcua' ? 'active' : ''}`} disabled={locked} onClick={() => onChange(project => ({ ...project, plc: { ...project.plc, mode: 'opcua' }, simulation: { ...project.simulation, speed: 1 } }))}><span className="radio-mark" /><div><strong>PLCSIM Advanced · OPC UA</strong><p>Le programme PLC testé pilote seul le modèle de procédé.</p></div><Wifi size={20} /></button></div>
      {plc.mode === 'opcua' && <div className="opcua-fields">
        <div className="information-strip"><ShieldCheck size={19} /><div>L’adresse virtuelle doit aussi figurer dans la politique locale du poste. Ce projet ne peut pas autoriser une cible à lui seul.</div></div>
        <label>Endpoint OPC UA<input className="mono" disabled={locked} value={plc.endpoint} onChange={event => update({ endpoint: event.target.value })} placeholder="opc.tcp://192.168.0.1:4840" /></label>
        <label>Identité attendue · Application URI<input className="mono" disabled={locked} value={plc.expected_application_uri} onChange={event => update({ expected_application_uri: event.target.value })} /></label>
        <label>Namespace URI (si nécessaire)<input className="mono" disabled={locked} value={plc.namespace_uri} onChange={event => update({ namespace_uri: event.target.value })} /></label>
        <label>Nom de la cible virtuelle approuvée<input disabled={locked} value={plc.approved_virtual_target} onChange={event => update({ approved_virtual_target: event.target.value })} placeholder="Instance PLCSIM du banc FAT" /></label>
        <div className="form-columns"><label>Politique de sécurité<select disabled={locked} value={plc.security_policy} onChange={event => update({ security_policy: event.target.value as Project['plc']['security_policy'] })}><option value="None">None · réseau virtuel isolé</option><option value="Basic256Sha256">Basic256Sha256</option></select></label><label>Délai de réponse (s)<input disabled={locked} type="number" min={.2} max={30} step={.1} value={plc.timeout_s} onChange={event => update({ timeout_s: Number(event.target.value) })} /></label></div>
        <details className="help-details"><summary>Certificats et authentification</summary><label>Empreinte SHA-256 du certificat serveur<input className="mono" disabled={locked} value={plc.server_certificate_sha256} onChange={event => update({ server_certificate_sha256: event.target.value })} /></label><label>Certificat client · chemin local<input className="mono" disabled={locked} value={plc.client_certificate} onChange={event => update({ client_certificate: event.target.value })} /></label><label>Clé privée client · chemin local<input className="mono" disabled={locked} value={plc.client_private_key} onChange={event => update({ client_private_key: event.target.value })} /></label><div className="form-columns"><label>Variable d’environnement · utilisateur<input disabled={locked} value={plc.username_env} onChange={event => update({ username_env: event.target.value })} placeholder="FAT_OPCUA_USERNAME" /></label><label>Variable d’environnement · mot de passe<input disabled={locked} value={plc.password_env} onChange={event => update({ password_env: event.target.value })} placeholder="FAT_OPCUA_PASSWORD" /></label></div><p>Les valeurs des secrets restent dans l’environnement du serveur. N’inscrivez aucun mot de passe dans le projet.</p></details>
      </div>}
      <h3>Pas de calcul</h3><div className="form-columns"><label>Pas du modèle (ms)<input disabled={locked} type="number" min={20} max={2000} step={10} value={project.simulation.step_ms} onChange={event => onChange(project => ({ ...project, simulation: { ...project.simulation, step_ms: Number(event.target.value) } }))} /></label><label>Vitesse de simulation<select disabled={locked || plc.mode === 'opcua'} value={project.simulation.speed} onChange={event => onChange(project => ({ ...project, simulation: { ...project.simulation, speed: Number(event.target.value) } }))}>{[.25, .5, 1, 2, 5, 10].map(speed => <option key={speed} value={speed}>× {speed}{speed === 1 ? ' · temps normal' : ''}</option>)}</select></label></div><p className="small-muted">L’interface s’actualise toutes les 500 ms. La vitesse accélérée sert à la démonstration ; l’échange PLC s’exécute à vitesse normale.</p>
    </div><aside className="connection-guide"><div className="connection-status-card"><span className={`connection-icon ${state?.connection.connected ? 'online' : ''}`}><Wifi size={22} /></span><h3>{state?.connection.connected ? 'Cible connectée' : 'En attente de connexion'}</h3><p className="mono">{state?.connection.target || (plc.mode === 'demo' ? 'Contrôleur local de démonstration' : plc.endpoint)}</p><div><span>Dernière acquisition</span><strong>{state?.connection.last_update ? new Date(state.connection.last_update).toLocaleTimeString('fr-CH') : '—'}</strong></div><div><span>Écritures du banc</span><strong>{fmt(state?.write_count ?? 0, 0)}</strong></div>{state?.connection.error && <p className="inline-error">{state.connection.error}</p>}</div>
      <h3>Mise en service du banc</h3><ol className="setup-checklist"><li><strong>Préparer une copie du projet TIA.</strong><p>Ajouter le DB d’échange et y relier les entrées/sorties de simulation.</p></li><li><strong>Démarrer PLCSIM Advanced en TCP/IP.</strong><p>Utiliser l’adaptateur Ethernet virtuel. Le serveur OPC UA doit être configuré dans la CPU virtuelle.</p></li><li><strong>Vérifier les variables et la cible.</strong><p>Renseigner les NodeId, types, autorisations locales et identité attendue.</p></li><li><strong>Démarrer et qualifier l’échange.</strong><p>Vérifier une mesure écrite et une commande lue sur la version Siemens installée.</p></li></ol>
      <div className="model-note"><strong>Sur perte de communication</strong><p>Le banc cesse les écritures et signale l’erreur. La reprise exige une action explicite. Aucun ordre RUN/STOP n’est envoyé à une CPU.</p></div>
    </aside></div>
    {validation && <div className={`validation-result ${validation.valid ? 'valid' : 'invalid'}`}><h3>{validation.valid ? <ShieldCheck size={19} /> : <CircleAlert size={19} />}{validation.valid ? 'Configuration locale cohérente' : 'Points à corriger avant l’essai'}</h3>{validation.errors.map((error, index) => <p key={`e-${index}`}><code>{error.path}</code> {error.message}</p>)}{validation.warnings.map((warning, index) => <p className="warning-text" key={`w-${index}`}><code>{warning.path}</code> {warning.message}</p>)}{validation.valid && <p>L’existence, le type et les droits des nœuds OPC UA seront contrôlés lors de la connexion.</p>}</div>}
    <details className="help-details model-reference"><summary>Hypothèses des modèles et bibliothèque d’équipements</summary>{catalog.map(item => <div className="model-reference-item" key={item.type}><h4>{item.label}</h4><p>{item.description}</p></div>)}<p>Les groupes de débit sont explicites. Les lignes P&ID ne résolvent pas un réseau hydraulique. Les essais ne constituent pas une validation de sécurité machine ou SIL.</p></details>
    <details className="help-details"><summary>Assistance TIA par Claude Code / Codex</summary><p>Le serveur MCP d’ingénierie s’exécute séparément du banc FAT. Utilisez la configuration et le guide fournis dans le dépôt : lecture seule par défaut, modifications dans une copie de développement, aperçu du diff et approbation humaine avant import ou compilation.</p><p>Un client IA hébergé peut transmettre les sources du projet hors du poste. Le mode FAT et la simulation locale ne nécessitent aucun modèle IA ni service cloud.</p></details>
  </section>;
}
