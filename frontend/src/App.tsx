import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, ArrowDownToLine, ArrowLeftRight, ChartNoAxesCombined, Check, ChevronDown, CircleAlert, CircleHelp, Clock3, FilePlus2, FolderOpen, ListChecks, LoaderCircle, Network, Pause, Play, RotateCcw, Save, Settings2, Shield, Square, Upload, Workflow, X } from 'lucide-react';
import { api, download, getProjectRevision, initSession, setProjectContext } from './api';
import { useModalKeyboard } from './useModalKeyboard';
import PidCanvas from './PidCanvas';
import { ConnectionPanel, ScenariosPanel, TrendChart, TrendsPanel, VariablesPanel } from './Panels';
import { STATUS_LABELS, fmt, type CatalogItem, type Project, type ProjectSummary, type Snapshot, type Tab, type Validation } from './types';

const TABS = [
  { key: 'pid' as const, label: 'P&ID', icon: Workflow },
  { key: 'tags' as const, label: 'Variables & mapping', icon: ArrowLeftRight },
  { key: 'scenarios' as const, label: 'Scénarios', icon: ListChecks },
  { key: 'trends' as const, label: 'Tendances & rapport', icon: ChartNoAxesCombined },
  { key: 'connection' as const, label: 'Connexion', icon: Settings2 },
];

function errorMessage(error: unknown): string { return error instanceof Error ? error.message : String(error); }
function elapsed(seconds: number): string { const minutes = Math.floor(seconds / 60); return `${String(minutes).padStart(2, '0')}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`; }

export default function App() {
  const [project, setProject] = useState<Project | null>(null);
  const [state, setState] = useState<Snapshot | null>(null);
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>('pid');
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [networkError, setNetworkError] = useState(false);
  const [projectConflict, setProjectConflict] = useState(false);
  const [notice, setNotice] = useState('');
  const [validation, setValidation] = useState<Validation | null>(null);
  const [scenarioId, setScenarioId] = useState('');
  const [scenarioPending, setScenarioPending] = useState(false);
  const [projectsModal, setProjectsModal] = useState<'open' | 'new' | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [newName, setNewName] = useState('');
  const [confirmTarget, setConfirmTarget] = useState(false);
  const [targetText, setTargetText] = useState('');
  const [showLivePanel, setShowLivePanel] = useState(true);
  const [bootAttempt, setBootAttempt] = useState(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const locked = state?.status === 'running' || state?.status === 'paused';
  const serviceUnavailable = networkError || projectConflict;
  const editorDisabled = Boolean(locked || busy || serviceUnavailable);
  useModalKeyboard(projectsModal !== null || confirmTarget, () => { if (!busy) { setProjectsModal(null); setConfirmTarget(false); } });

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setInitializing(true);
    const boot = async () => {
      try {
        await initSession();
        const [projectData, catalogData, stateData] = await Promise.all([
          api<Project>('/project', 'GET', undefined, controller.signal),
          api<CatalogItem[]>('/catalog', 'GET', undefined, controller.signal),
          api<Snapshot>('/state', 'GET', undefined, controller.signal),
        ]);
        if (active) {
          const mismatch = Boolean((stateData.project_id && stateData.project_id !== projectData.id) || (stateData.project_revision && getProjectRevision() && stateData.project_revision !== getProjectRevision()));
          setProject(projectData); setCatalog(catalogData); setState(mismatch ? null : stateData);
          setError(null); setNetworkError(false); setProjectConflict(mismatch); setDirty(false);
          setScenarioId(''); setScenarioPending(false);
        }
      } catch (error) { if (active) setError(errorMessage(error)); }
      finally { if (active) setInitializing(false); }
    };
    void boot();
    return () => { active = false; controller.abort(); };
  }, [bootAttempt]);

  useEffect(() => {
    if (initializing || !project) return;
    let active = true;
    let inFlight = false;
    const controller = new AbortController();
    const poll = async () => {
      if (inFlight || !active) return;
      inFlight = true;
      try {
        const requestedRevision = getProjectRevision();
        const data = await api<Snapshot>('/state', 'GET', undefined, controller.signal);
        if (active) {
          if (getProjectRevision() !== requestedRevision) return; // a project save completed during this poll
          const mismatch = Boolean((data.project_id && data.project_id !== project.id) || (data.project_revision && requestedRevision && data.project_revision !== requestedRevision));
          setProjectConflict(mismatch); setNetworkError(false);
          if (!mismatch) setState(data);
        }
      }
      catch { if (active) setNetworkError(true); }
      finally { inFlight = false; }
    };
    const timer = setInterval(() => void poll(), 500);
    return () => { active = false; controller.abort(); clearInterval(timer); };
  }, [initializing, project?.id]);

  useEffect(() => { setProjectContext(project?.id ?? ''); }, [project?.id]);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => { if (dirty || scenarioPending) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', beforeUnload);
    return () => window.removeEventListener('beforeunload', beforeUnload);
  }, [dirty, scenarioPending]);

  useEffect(() => { if (!notice) return; const timer = setTimeout(() => setNotice(''), 4500); return () => clearTimeout(timer); }, [notice]);

  const onChange = useCallback((update: (project: Project) => Project) => {
    setProject(current => current ? update(current) : current);
    setDirty(true); setValidation(null);
  }, []);

  const saveProject = useCallback(async (): Promise<Project> => {
    if (!project) throw new Error('Aucun projet chargé.');
    if (scenarioPending) throw new Error('Appliquez les étapes JSON du scénario avant de sauvegarder.');
    const saved = await api<Project>('/project', 'PUT', project);
    setProject(saved); setDirty(false); return saved;
  }, [project, scenarioPending]);

  const act = async (action: () => Promise<void>) => {
    if (busy) return;
    setBusy(true); setError(null);
    try { await action(); } catch (error) { setError(errorMessage(error)); } finally { setBusy(false); }
  };

  const save = () => act(async () => { await saveProject(); setNotice('Projet enregistré.'); });
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        if (!editorDisabled && !scenarioPending) void save();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [saveProject, editorDisabled, scenarioPending, busy]);

  const replaceProject = (loaded: Project) => {
    setProject(loaded); setProjectConflict(false); setDirty(false); setScenarioId(''); setScenarioPending(false); setValidation(null); setProjectsModal(null); setActiveTab('pid');
    void api<Snapshot>('/state').then(setState).catch(error => setError(errorMessage(error)));
  };
  const canReplace = () => !(dirty || scenarioPending) || window.confirm('Les modifications non enregistrées seront perdues. Continuer ?');
  const openProjects = () => act(async () => { setProjects(await api<ProjectSummary[]>('/projects')); setProjectsModal('open'); });
  const newProject = () => act(async () => { if (canReplace()) { replaceProject(await api<Project>('/projects', 'POST', { name: newName.trim() })); setNotice('Nouveau projet créé.'); } });
  const loadProject = (id: string) => act(async () => { if (canReplace()) replaceProject(await api<Project>(`/projects/${encodeURIComponent(id)}/load`, 'POST', {})); });
  const loadDemo = () => act(async () => { if (canReplace()) { replaceProject(await api<Project>('/demo/load', 'POST', {})); setNotice('Démonstration TK-101 chargée.'); } });
  const importFile = async (file: File) => act(async () => {
    if (!canReplace()) return;
    if (file.size > 5 * 1024 * 1024) throw new Error('Le fichier projet dépasse 5 Mo.');
    const data: unknown = JSON.parse(await file.text());
    replaceProject(await api<Project>('/project/import', 'POST', data)); setNotice('Projet importé.');
  });
  const validate = () => act(async () => { await saveProject(); const result = await api<Validation>('/validate'); setValidation(result); if (!result.valid) setActiveTab('connection'); else setNotice('Configuration locale validée.'); });
  const start = (confirmation?: string) => act(async () => {
    if (!project) return;
    await saveProject();
    const result = await api<Validation>('/validate'); setValidation(result);
    if (!result.valid) { setActiveTab('connection'); throw new Error(`Le projet contient ${result.errors.length} erreur(s). Corrigez les points indiqués dans Connexion.`); }
    if (project.plc.mode === 'opcua' && !confirmation) { setTargetText(''); setConfirmTarget(true); return; }
    setState(await api<Snapshot>('/run/start', 'POST', { ...(scenarioId ? { scenario_id: scenarioId } : {}), ...(confirmation ? { target_confirmation: confirmation } : {}) }));
    setConfirmTarget(false); setNotice('Essai démarré.');
  });
  const control = (action: 'pause' | 'resume' | 'stop' | 'reset') => act(async () => {
    if (action === 'reset' && !window.confirm('Réinitialiser les valeurs, le modèle et les forçages pour un nouvel essai ? Les traces déjà enregistrées restent dans l’historique.')) return;
    setState(await api<Snapshot>(`/run/${action}`, 'POST', {}));
  });
  const changeTab = (tab: Tab) => {
    if (activeTab === 'scenarios' && scenarioPending && tab !== 'scenarios') {
      if (!window.confirm('Les étapes JSON n’ont pas été appliquées. Les abandonner ?')) return;
      setScenarioPending(false);
    }
    setActiveTab(tab);
    window.scrollTo({ top: 0 });
  };
  const exportProject = () => act(async () => { if (dirty) await saveProject(); download('/project/download'); });
  const exportMapping = () => act(async () => { if (dirty) await saveProject(); download('/mapping'); });
  const downloadDraft = () => {
    if (!project) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(project, null, 2) + '\n'], { type: 'application/json' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${project.id}-brouillon.json`;
    anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const importMapping = async (csv: string) => {
    await act(async () => { await saveProject(); const loaded = await api<Project>('/mapping', 'POST', { csv }); setProject(loaded); setDirty(false); setValidation(null); setNotice('Mapping importé et enregistré.'); });
  };

  if (initializing || !project) return <div className="boot-screen"><div className="brand-mark"><Workflow size={27} /></div><h1>FAT Studio</h1><p>Le banc de simulation, sur votre poste.</p>{initializing ? <div className="boot-loading"><LoaderCircle className="spin" size={20} />Connexion au service local…</div> : <><div className="boot-error"><CircleAlert size={21} /><span>{error}</span></div><button className="button primary" onClick={() => setBootAttempt(value => value + 1)}>Réessayer</button><p className="small-muted">Démarrez le serveur FAT Studio, puis rechargez cette page.</p></>}</div>;

  const currentStatus = state?.status ?? 'idle';
  const expectedTarget = `${project.plc.approved_virtual_target} @ ${project.plc.endpoint}`;
  const scenarioCompleted = state?.scenario.state === 'completed';
  const totalForces = Object.values(state?.tags ?? {}).filter(tag => tag.forced).length;
  const totalFaults = Object.values(state?.faults ?? {}).reduce((count, faults) => count + Object.keys(faults).length, 0);
  const props = { project, state, locked: editorDisabled, online: !serviceUnavailable && !busy, onChange, onError: setError, onSnapshot: setState };
  return <div className="app-shell">
    <header className="topbar"><div className="brand"><div className="brand-mark"><Workflow size={24} strokeWidth={2} /></div><div><strong>FAT<span>STUDIO</span></strong><small>BANC DE SIMULATION LOCAL</small></div></div>
      <div className="mode-badge"><Shield size={14} /><span>MODE FAT</span><span className="mode-divider" /><strong>{project.plc.mode === 'demo' ? 'DÉMONSTRATION' : 'PLCSIM ADVANCED'}</strong></div>
      <div className="run-controls"><div className="run-clock"><Clock3 size={15} /><span>{elapsed(state?.sim_time_s ?? 0)}</span></div>
        <button className="run-button start-button" disabled={busy || serviceUnavailable || scenarioPending || currentStatus === 'running' || scenarioCompleted} onClick={() => void (currentStatus === 'paused' ? control('resume') : start())}><Play size={16} fill="currentColor" />{scenarioCompleted ? 'Terminé' : currentStatus === 'paused' ? 'Reprendre' : 'Démarrer'}</button>
        <button className="run-button" title="Mettre en pause" disabled={busy || serviceUnavailable || currentStatus !== 'running'} onClick={() => void control('pause')} aria-label="Mettre en pause"><Pause size={18} /></button>
        <button className="run-button stop-button" title="Arrêter l’essai" disabled={busy || serviceUnavailable || !['running', 'paused', 'error'].includes(currentStatus)} onClick={() => void control('stop')} aria-label="Arrêter l’essai"><Square size={15} fill="currentColor" /></button>
        <button className="run-button" title="Réinitialiser le modèle" disabled={busy || serviceUnavailable || currentStatus === 'running'} onClick={() => void control('reset')} aria-label="Réinitialiser le modèle"><RotateCcw size={17} /></button>
      </div>
    </header>

    <div className="projectbar"><div className="project-identity"><span className="project-icon"><FolderOpen size={22} /></span><div><input className="project-name" disabled={editorDisabled} aria-label="Nom du projet" value={project.name} onChange={event => onChange(project => ({ ...project, name: event.target.value }))} /><div className="project-subtitle"><span>{project.equipment.length} équipements</span><span>·</span><span>{project.tags.length} variables</span><span className={dirty ? 'unsaved-text' : 'saved-text'}>{dirty ? '• Modifications non enregistrées' : <><Check size={11} /> Enregistré</>}</span></div></div></div>
      <div className="project-actions"><button className="button ghost" disabled={editorDisabled} onClick={() => { setNewName(''); setProjectsModal('new'); }}><FilePlus2 size={16} /><span>Nouveau</span></button><button className="button ghost" disabled={editorDisabled} onClick={() => void openProjects()}><FolderOpen size={16} /><span>Ouvrir</span></button><button className="button ghost" disabled={editorDisabled} onClick={() => fileInput.current?.click()}><Upload size={16} /><span>Importer</span></button><button className="button ghost" disabled={busy || serviceUnavailable || scenarioPending || (dirty && editorDisabled)} onClick={() => void exportProject()}><ArrowDownToLine size={16} /><span>Exporter</span></button><span className="toolbar-separator" /><button className="button save-button" disabled={editorDisabled || scenarioPending} onClick={() => void save()}><Save size={16} /><span>Enregistrer</span></button></div>
      <input ref={fileInput} type="file" accept=".json,application/json" hidden onChange={event => { const file = event.target.files?.[0]; if (file) void importFile(file); event.target.value = ''; }} />
    </div>

    <div className="tabsbar"><nav aria-label="Sections du banc FAT">{TABS.map(tab => <button key={tab.key} className={`tab-button ${activeTab === tab.key ? 'active' : ''}`} onClick={() => changeTab(tab.key)}><tab.icon size={16} /><span>{tab.label}</span>{tab.key === 'tags' && <small>{project.tags.length}</small>}</button>)}</nav><div className="runtime-status"><span className={`status-badge ${serviceUnavailable ? 'error' : currentStatus}`}><span />{projectConflict ? 'Autre projet actif' : networkError ? 'Service indisponible' : STATUS_LABELS[currentStatus]}</span><button className="icon-button" title="Guide de mise en service" onClick={() => changeTab('connection')} aria-label="Ouvrir le guide de mise en service"><CircleHelp size={18} /></button></div></div>

    {projectConflict && <div className="banner error-banner" role="alert"><CircleAlert size={18} /><span>Le projet actif a changé dans un autre onglet. Vos modifications restent dans cet onglet ; les commandes sont bloquées pour éviter toute action sur une autre cible.</span><div className="button-row"><button className="button compact-button" onClick={downloadDraft}>Télécharger mon brouillon</button><button className="button compact-button" onClick={() => { if (canReplace()) setBootAttempt(value => value + 1); }}>Recharger le projet actif</button></div></div>}
    {networkError && <div className="banner error-banner" role="alert"><CircleAlert size={18} /><span>Connexion au service local perdue. Les valeurs affichées sont anciennes. Vérifiez le serveur ; les commandes sont désactivées.</span></div>}
    {error && <div className="banner error-banner" role="alert"><CircleAlert size={18} /><pre>{error}</pre><button className="icon-button" onClick={() => setError(null)} aria-label="Fermer le message d’erreur"><X size={16} /></button></div>}
    {state?.error && state.error !== error && <div className="banner error-banner" role="alert"><CircleAlert size={18} /><span>{state.error}</span></div>}
    {notice && <div className="toast" role="status"><Check size={17} />{notice}<button className="icon-button" onClick={() => setNotice('')} aria-label="Fermer la notification"><X size={15} /></button></div>}

    <main>
      {activeTab === 'pid' && <>
        <div className="workspace-toolbar"><div className="workspace-label"><span className="small-dot" /><strong>Vue procédé</strong><span>P&ID interactif</span></div><div className="scenario-selector"><ListChecks size={15} /><label htmlFor="active-scenario">Scénario</label><select id="active-scenario" value={scenarioId} disabled={editorDisabled} onChange={event => setScenarioId(event.target.value)}><option value="">Essai libre</option>{project.scenarios.map(scenario => <option key={scenario.id} value={scenario.id}>{scenario.name}</option>)}</select></div></div>
        <PidCanvas {...props} catalog={catalog} key={project.id} />
        <div className="live-panel-heading"><button onClick={() => setShowLivePanel(value => !value)}><Activity size={16} />Acquisition de l’essai<ChevronDown size={15} className={showLivePanel ? 'rotate-180' : ''} /></button><div>{totalForces > 0 && <span className="forced-counter">{totalForces} forçage{totalForces > 1 ? 's' : ''}</span>}{totalFaults > 0 && <span className="fault-counter">{totalFaults} défaut{totalFaults > 1 ? 's' : ''}</span>}<button className="text-link" onClick={() => changeTab('trends')}>Ouvrir tendances & rapport →</button></div></div>
        {showLivePanel && <div className="live-overview"><div><TrendChart project={project} state={state} compact /></div><div className="live-events"><div className="live-events-title">Derniers événements</div>{(state?.events ?? []).slice(-4).reverse().map(event => <div key={event.id}><time>{fmt(event.sim_time_s)} s</time><p>{event.message}</p></div>)}{!state?.events.length && <p className="small-muted">Démarrez l’essai pour suivre les actions et les diagnostics.</p>}</div></div>}
      </>}
      {activeTab === 'tags' && <VariablesPanel {...props} onImport={importMapping} onExport={exportMapping} />}
      {activeTab === 'scenarios' && <ScenariosPanel {...props} selectedId={scenarioId} onSelect={setScenarioId} onDraftChange={setScenarioPending} />}
      {activeTab === 'trends' && <TrendsPanel {...props} />}
      {activeTab === 'connection' && <ConnectionPanel {...props} validation={validation} onValidate={validate} catalog={catalog} />}
    </main>

    <footer className="statusbar"><div><span className={`small-dot ${state?.connection.connected && !serviceUnavailable ? 'green' : ''}`} /><strong>{project.plc.mode === 'demo' ? 'Contrôleur de démonstration' : 'OPC UA · ' + (state?.connection.connected ? 'connecté' : 'déconnecté')}</strong><span className="footer-divider" /><span>{project.plc.mode === 'demo' ? 'Aucun automate raccordé' : state?.connection.target || project.plc.endpoint}</span></div><div><span>Pas : {project.simulation.step_ms} ms</span><span>Vitesse : ×{project.simulation.speed}</span><span>{fmt(state?.write_count ?? 0, 0)} écritures</span><Network size={13} /><span>Local · 127.0.0.1</span></div></footer>

    {projectsModal && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="projects-modal-title"><div className="modal-heading"><h2 id="projects-modal-title">{projectsModal === 'new' ? 'Nouveau projet FAT' : 'Ouvrir un projet'}</h2><button className="icon-button" onClick={() => setProjectsModal(null)} aria-label="Fermer la fenêtre"><X size={19} /></button></div>
      {projectsModal === 'new' ? <form onSubmit={event => { event.preventDefault(); void newProject(); }}><label>Nom du projet<input autoFocus value={newName} onChange={event => setNewName(event.target.value)} placeholder="Ex. Skid de dosage — FAT 01" maxLength={120} required /></label><p className="small-muted">Le projet commence avec un canevas vide et le mode démonstration local.</p><div className="modal-actions"><button type="button" className="button" onClick={() => setProjectsModal(null)}>Annuler</button><button className="button primary" disabled={busy || !newName.trim()}><PlusIcon />Créer le projet</button></div></form>
        : <><div className="project-list">{projects.map(entry => <button key={entry.id} onClick={() => void loadProject(entry.id)} disabled={busy}><FolderOpen size={20} /><span><strong>{entry.name}</strong><small>{entry.updated_at ? new Date(entry.updated_at).toLocaleString('fr-CH') : entry.id}</small></span>{entry.id === project.id && <span className="type-label">Ouvert</span>}</button>)}{!projects.length && <p className="empty-inline">Aucun projet enregistré.</p>}</div><div className="demo-project"><div><strong>Exemple TK-101</strong><p>Cuve, pompe, vannes, instruments et scénarios de référence.</p></div><button className="button" disabled={busy} onClick={() => void loadDemo()}>Charger la démo</button></div></>}
    </section></div>}

    {confirmTarget && <div className="modal-backdrop"><section className="modal target-modal" role="dialog" aria-modal="true" aria-labelledby="target-title"><div className="modal-heading"><h2 id="target-title">Confirmer la cible virtuelle</h2><button className="icon-button" onClick={() => setConfirmTarget(false)} aria-label="Annuler la connexion"><X size={18} /></button></div><div className="target-identity"><span>INSTANCE APPROUVÉE</span><strong>{project.plc.approved_virtual_target || 'Nom non renseigné'}</strong><code>{expectedTarget}</code><small>{project.plc.expected_application_uri}</small></div><p>Le banc va lire les commandes PLC et écrire uniquement les entrées simulées autorisées. Vérifiez que cette cible appartient à l’instance PLCSIM Advanced de votre poste.</p><label>Recopiez exactement la cible pour confirmer<input autoFocus className="mono" value={targetText} onChange={event => setTargetText(event.target.value)} placeholder={expectedTarget} /></label><div className="modal-actions"><button className="button" onClick={() => setConfirmTarget(false)}>Annuler</button><button className="button primary" disabled={busy || targetText !== expectedTarget} onClick={() => void start(targetText)}><Shield size={16} />Connecter et démarrer</button></div></section></div>}
  </div>;
}

function PlusIcon() { return <FilePlus2 size={16} />; }
