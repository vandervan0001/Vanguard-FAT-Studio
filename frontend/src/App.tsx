import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, ArrowDownToLine, ArrowLeftRight, ChartNoAxesCombined, Check, ChevronDown, CircleAlert, CircleHelp, Clock3, FilePlus2, FolderOpen, ListChecks, LoaderCircle, Maximize2, Minimize2, Network, Pause, Play, RotateCcw, Save, Settings2, Shield, Square, Upload, Workflow, X } from 'lucide-react';
import { api, downloadArchive, downloadMapping, downloadText, getMutationVersion, getProjectContext, getProjectRevision, initSession, setRunContext } from './api';
import { useModalKeyboard } from './useModalKeyboard';
import PidCanvas from './PidCanvas';
import { ScenarioRun } from './ScenarioRun';
import { ConnectionPanel, ScenariosPanel, TrendChart, TrendsPanel, VariablesPanel } from './Panels';
import { STATUS_LABELS, fmt, type CatalogItem, type Project, type ProjectPackage, type ProjectSummary, type ReportDraft, type ScenarioDraft, type ScenarioImportMode, type ScenarioPackage, type Snapshot, type Tab, type Validation, type WorkspaceSummary } from './types';

const TABS = [
  { key: 'pid' as const, label: 'P&ID', icon: Workflow },
  { key: 'tags' as const, label: 'Variables & mapping', icon: ArrowLeftRight },
  { key: 'scenarios' as const, label: 'Scénarios', icon: ListChecks },
  { key: 'trends' as const, label: 'Tendances & rapport', icon: ChartNoAxesCombined },
  { key: 'connection' as const, label: 'Connexion', icon: Settings2 },
];

function errorMessage(error: unknown): string { return error instanceof Error ? error.message : String(error); }
function elapsed(seconds: number): string { const minutes = Math.floor(seconds / 60); return `${String(minutes).padStart(2, '0')}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`; }
function reportFor(state: Snapshot | null): ReportDraft { return { runId: state?.run_id ?? null, verdict: state?.result?.verdict ?? 'not_evaluated', comment: state?.result?.comment ?? '', marker: '', resultDirty: false, saved: false }; }

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
  const [scenarioDraft, setScenarioDraft] = useState<ScenarioDraft | null>(null);
  const [guidedObservations, setGuidedObservations] = useState<Record<string, string>>({});
  const scenarioPending = scenarioDraft !== null;
  const [reportDraft, setReportDraft] = useState<ReportDraft>(() => reportFor(null));
  const [projectsModal, setProjectsModal] = useState<'open' | 'new' | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [newName, setNewName] = useState('');
  const [confirmTarget, setConfirmTarget] = useState(false);
  const [targetText, setTargetText] = useState('');
  const [showLivePanel, setShowLivePanel] = useState(false);
  const [viewRequest, setViewRequest] = useState(0);
  const [presentation, setPresentation] = useState(false);
  const [scenarioPanelVersion, setScenarioPanelVersion] = useState(0);
  const [bootAttempt, setBootAttempt] = useState(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const archiveInput = useRef<HTMLInputElement>(null);
  const stateRef = useRef<Snapshot | null>(null);
  const latestSnapshotTime = useRef(0);
  const actionBusy = useRef(false);
  const guidedPending = state?.guided_steps?.some(step => step.state === 'applied' && (guidedObservations[`${state.run_id}:${step.id}`] ?? '') !== step.observation) ?? false;
  const reportPending = reportDraft.resultDirty || reportDraft.marker !== '' || guidedPending;
  const locked = state?.status === 'running';
  const serviceUnavailable = networkError || projectConflict;
  const editorDisabled = Boolean(locked || busy || serviceUnavailable);
  useModalKeyboard(projectsModal !== null || confirmTarget, () => { if (!busy) { setProjectsModal(null); setConfirmTarget(false); } });

  const receiveSnapshot = useCallback((data: Snapshot) => {
    const time = Date.parse(data.wall_time);
    if (time < latestSnapshotTime.current) return;
    latestSnapshotTime.current = time;
    const mismatch = Boolean((data.project_id && data.project_id !== getProjectContext()) || (data.project_revision && getProjectRevision() && data.project_revision !== getProjectRevision()));
    if (mismatch) { setProjectConflict(true); return; }
    // A delayed poll or response must never put the screen back before a confirmed action.
    if (stateRef.current && Date.parse(data.wall_time) < Date.parse(stateRef.current.wall_time)) return;
    stateRef.current = data;
    setRunContext(data.run_id);
    setState(data);
    setProjectConflict(false); setNetworkError(false);
  }, []);

  const refreshState = useCallback(async () => {
    try { receiveSnapshot(await api<Snapshot>('/state')); }
    catch (error) { setNetworkError(true); throw error; }
  }, [receiveSnapshot]);

  useEffect(() => {
    setReportDraft(current => {
      if (current.runId !== (state?.run_id ?? null)) return current.resultDirty || current.marker ? current : reportFor(state);
      if (current.resultDirty) return current;
      const result = reportFor(state);
      return { ...current, verdict: result.verdict, comment: result.comment, saved: current.saved && current.verdict === result.verdict && current.comment === result.comment };
    });
  }, [state?.run_id, state?.result?.verdict, state?.result?.comment]);
  const changeReportDraft = useCallback((update: (draft: ReportDraft) => ReportDraft) => setReportDraft(update), []);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    setInitializing(true);
    const boot = async () => {
      try {
        await initSession(controller.signal);
        const [projectData, catalogData, stateData] = await Promise.all([
          api<Project>('/project', 'GET', undefined, controller.signal),
          api<CatalogItem[]>('/catalog', 'GET', undefined, controller.signal),
          api<Snapshot>('/state', 'GET', undefined, controller.signal),
        ]);
        if (active) {
          const mismatch = Boolean((stateData.project_id && stateData.project_id !== projectData.id) || (stateData.project_revision && getProjectRevision() && stateData.project_revision !== getProjectRevision()));
          stateRef.current = null; latestSnapshotTime.current = 0; setState(null);
          setProject(projectData); setCatalog(catalogData);
          if (!mismatch) receiveSnapshot(stateData);
          setError(null); setNetworkError(false); setProjectConflict(mismatch); setDirty(false);
          setScenarioId(!mismatch ? stateData.scenario.id ?? '' : ''); setScenarioDraft(null);
        }
      } catch (error) { if (active) setError(controller.signal.aborted ? 'Le service local ne répond pas. Vérifiez le serveur puis réessayez.' : errorMessage(error)); }
      finally { clearTimeout(timeout); if (active) setInitializing(false); }
    };
    void boot();
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [bootAttempt, receiveSnapshot]);

  useEffect(() => {
    if (initializing || !project) return;
    let active = true;
    let inFlight = false;
    const controller = new AbortController();
    const poll = async () => {
      if (inFlight || !active) return;
      inFlight = true;
      const requestController = new AbortController();
      const cancel = () => requestController.abort();
      controller.signal.addEventListener('abort', cancel, { once: true });
      const timeout = setTimeout(cancel, 5000);
      const requestedMutation = getMutationVersion();
      try {
        const requestedRevision = getProjectRevision();
        const data = await api<Snapshot>('/state', 'GET', undefined, requestController.signal);
        if (active) {
          if (getProjectRevision() !== requestedRevision || getMutationVersion() !== requestedMutation) return;
          receiveSnapshot(data);
        }
      }
      catch { if (active && getMutationVersion() === requestedMutation) setNetworkError(true); }
      finally { clearTimeout(timeout); controller.signal.removeEventListener('abort', cancel); inFlight = false; }
    };
    const timer = setInterval(() => void poll(), 500);
    return () => { active = false; controller.abort(); clearInterval(timer); };
  }, [initializing, project?.id, receiveSnapshot]);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => { if (dirty || scenarioPending || reportPending) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', beforeUnload);
    return () => window.removeEventListener('beforeunload', beforeUnload);
  }, [dirty, scenarioPending, reportPending]);

  useEffect(() => { if (!notice) return; const timer = setTimeout(() => setNotice(''), 4500); return () => clearTimeout(timer); }, [notice]);

  const onChange = useCallback((update: (project: Project) => Project) => {
    setProject(current => current ? update(current) : current);
    setDirty(true); setValidation(null);
  }, []);

  const saveProject = useCallback(async (): Promise<Project> => {
    if (!project) throw new Error('Aucun projet chargé.');
    if (scenarioPending) throw new Error('Appliquez les étapes JSON du scénario avant de sauvegarder.');
    if (!dirty) return project;
    const saved = await api<Project>('/project', 'PUT', project);
    setProject(saved); setDirty(false);
    stateRef.current = null; setState(null);
    await refreshState();
    return saved;
  }, [project, scenarioPending, dirty, refreshState]);

  const act = async (action: () => Promise<void>) => {
    if (actionBusy.current) return;
    actionBusy.current = true;
    setBusy(true); setError(null);
    try { await action(); } catch (error) { setError(errorMessage(error)); } finally { actionBusy.current = false; setBusy(false); }
  };

  const save = () => act(async () => { const wasPaused = stateRef.current?.status === 'paused' && dirty; await saveProject(); setNotice(wasPaused ? 'Modifications appliquées. Essai précédent conservé ; démarrez un nouvel essai.' : 'Projet enregistré.'); });
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

  const replaceProject = async (loaded: Project) => {
    setProject(loaded); setProjectConflict(false); setDirty(false); setScenarioId(''); setScenarioDraft(null); setValidation(null); setProjectsModal(null); setActiveTab('pid');
    stateRef.current = null; setState(null);
    await refreshState();
  };
  const canReplace = () => !(dirty || scenarioPending) || window.confirm('Les modifications non enregistrées seront perdues. Continuer ?');
  const openProjects = () => act(async () => { const [projects, workspaces] = await Promise.all([api<ProjectSummary[]>('/projects'), api<WorkspaceSummary[]>('/workspaces')]); setProjects(projects); setWorkspaces(workspaces); setProjectsModal('open'); });
  const openWorkspace = (id: string) => act(async () => { if (canReplace()) { await replaceProject(await api<Project>(`/workspaces/${encodeURIComponent(id)}/open`, 'POST', {})); setNotice('Dossier FAT ouvert au repos.'); } });
  const exportArchive = () => act(async () => { const saved = await saveProject(); await downloadArchive(`${saved.id}.fat.zip`); setNotice('Archive FAT téléchargée.'); });
  const importArchive = (file: File) => act(async () => {
    if (!canReplace()) return;
    if (file.size > 100 * 1024 * 1024) throw new Error('L’archive FAT dépasse 100 Mo.');
    await replaceProject(await api<Project>('/project/archive/import', 'POST', file));
    setNotice('Archive restaurée dans un nouveau dossier. Ancien espace conservé ; aucun essai démarré.');
  });
  const newProject = () => act(async () => { if (canReplace()) { await replaceProject(await api<Project>('/projects', 'POST', { name: newName.trim() })); setNotice('Nouveau projet créé.'); } });
  const loadProject = (id: string) => act(async () => { if (canReplace()) await replaceProject(await api<Project>(`/projects/${encodeURIComponent(id)}/load`, 'POST', {})); });
  const loadDemo = () => act(async () => { if (canReplace()) { await replaceProject(await api<Project>('/demo/load', 'POST', {})); setNotice('Démonstration TK-101 chargée.'); } });
  const loadPilot = () => act(async () => { if (canReplace()) { await replaceProject(await api<Project>('/pilot/load', 'POST', {})); setNotice('Laboratoire chargé · commandes manuelles en démonstration, aucun PLC connecté.'); } });
  const importFile = async (file: File) => act(async () => {
    if (!canReplace()) return;
    if (file.size > 5 * 1024 * 1024) throw new Error('Le fichier projet dépasse 5 Mo.');
    const data: unknown = JSON.parse(await file.text());
    await replaceProject(await api<Project>('/project/import', 'POST', data)); setNotice('Projet importé.');
  });
  const validate = () => act(async () => { await saveProject(); const result = await api<Validation>('/validate'); setValidation(result); if (!result.valid) setActiveTab('connection'); else setNotice('Configuration locale validée.'); });
  const start = (confirmation?: string) => act(async () => {
    if (!project) return;
    await saveProject();
    const result = await api<Validation>('/validate'); setValidation(result);
    if (!result.valid) { setActiveTab('connection'); throw new Error(`Le projet contient ${result.errors.length} erreur(s). Corrigez les points indiqués dans Connexion.`); }
    if (project.plc.mode === 'opcua' && !confirmation) { setTargetText(''); setConfirmTarget(true); return; }
    receiveSnapshot(await api<Snapshot>('/run/start', 'POST', { ...(scenarioId ? { scenario_id: scenarioId } : {}), ...(confirmation ? { target_confirmation: confirmation } : {}) }));
    setConfirmTarget(false); setNotice('Essai démarré.');
  });
  const control = (action: 'pause' | 'resume' | 'stop' | 'reset') => act(async () => {
    if (action === 'reset' && !window.confirm('Réinitialiser les valeurs, le modèle et les forçages pour un nouvel essai ? Les traces déjà enregistrées restent dans l’historique.')) return;
    receiveSnapshot(await api<Snapshot>(`/run/${action}`, 'POST', {}));
  });
  const changeTab = (tab: Tab) => {
    if (activeTab === 'scenarios' && scenarioPending && tab !== 'scenarios') {
      if (!window.confirm('Les étapes JSON n’ont pas été appliquées. Les abandonner ?')) return;
      setScenarioDraft(null);
    }
    setActiveTab(tab);
    window.scrollTo({ top: 0 });
  };
  const exportProject = () => act(async () => { const saved = await saveProject(); const packaged = await api<ProjectPackage>('/project/download'); downloadText(JSON.stringify(packaged, null, 2) + '\n', `${saved.id}.json`); });
  const exportScenarios = (id?: string) => act(async () => {
    const saved = await saveProject();
    const packaged = await api<ScenarioPackage>(id ? `/scenarios/${encodeURIComponent(id)}/export` : '/scenarios/export');
    downloadText(JSON.stringify(packaged, null, 2) + '\n', `${id ?? saved.id}-scenarios.json`);
  });
  const importScenarios = (file: File, mode: ScenarioImportMode) => act(async () => {
    if (file.size > 5 * 1024 * 1024) throw new Error('Le fichier de scénarios dépasse 5 Mo.');
    const packaged: unknown = JSON.parse(await file.text());
    if (mode === 'replace' && !window.confirm('Remplacer tous les scénarios de ce projet par ceux du fichier ? Les équipements et variables seront conservés.')) return;
    await saveProject();
    const loaded = await api<Project>('/scenarios/import', 'POST', { package: packaged, mode });
    setProject(loaded); setDirty(false); setValidation(null); setScenarioDraft(null);
    setScenarioId(current => loaded.scenarios.some(scenario => scenario.id === current) ? current : '');
    setScenarioPanelVersion(value => value + 1);
    stateRef.current = null; setState(null); await refreshState();
    setNotice(`${loaded.scenarios.length} scénario(s) disponibles · import enregistré.`);
  });
  const exportMapping = () => act(async () => { if (dirty) await saveProject(); await downloadMapping(); });
  const downloadDraft = () => {
    if (!project) return;
    downloadText(JSON.stringify({ format: 'fat-studio/project', version: '1.0', project }, null, 2) + '\n', `${project.id}-brouillon.json`);
  };
  const importMapping = async (csv: string) => {
    await act(async () => { await saveProject(); const loaded = await api<Project>('/mapping', 'POST', { csv }); setProject(loaded); setDirty(false); setValidation(null); stateRef.current = null; setState(null); await refreshState(); setNotice('Mapping importé et enregistré.'); });
  };
  const chooseScenario = (id: string) => {
    if (editorDisabled) return;
    if (state?.status === 'paused' && id !== state.scenario.id) setDirty(true);
    setScenarioId(id);
  };

  if (initializing || !project) return <div className="boot-screen"><img className="boot-logo" src="/brand/logo_vanguard.png" alt="Vanguard" width={64} height={64} /><h1>Vanguard FAT Studio</h1><p>Le banc de simulation, sur votre poste.</p>{initializing ? <div className="boot-loading"><LoaderCircle className="spin" size={20} />Connexion au service local…</div> : <><div className="boot-error"><CircleAlert size={21} /><span>{error}</span></div><button className="button primary" onClick={() => setBootAttempt(value => value + 1)}>Réessayer</button><p className="small-muted">Démarrez le serveur Vanguard FAT Studio, puis rechargez cette page.</p></>}</div>;

  const currentStatus = state?.status ?? 'idle';
  const expectedTarget = `${project.plc.approved_virtual_target} @ ${project.plc.endpoint}`;
  const scenarioCompleted = state?.scenario.state === 'completed';
  const totalForces = Object.values(state?.tags ?? {}).filter(tag => tag.forced).length;
  const totalFaults = Object.values(state?.faults ?? {}).reduce((count, faults) => count + Object.keys(faults).length, 0);
  const props = { project, state, locked: editorDisabled, online: !serviceUnavailable && !busy, onChange, onError: setError, onSnapshot: receiveSnapshot };
  const displayedScenarioId = locked ? state?.scenario.id ?? '' : scenarioId;
  const activeScenario = project.scenarios.find(scenario => scenario.id === displayedScenarioId) ?? null;
  return <div className={`app-shell ${presentation && activeTab === 'pid' && currentStatus !== 'paused' ? 'presentation-mode' : ''}`}>
    <header className="topbar"><div className="brand" aria-label="Vanguard FAT Studio"><img className="brand-wordmark" src="/brand/logo_vanguard_wordmark_horizontal.png" alt="Vanguard" width={154} height={40} /><div className="brand-product"><strong>FAT Studio</strong><small>BANC FAT LOCAL</small></div></div>
      <div className="mode-badge"><Shield size={14} /><span>MODE FAT</span><span className="mode-divider" /><strong>{project.plc.mode === 'demo' ? 'DÉMONSTRATION' : 'PLCSIM ADVANCED'}</strong></div>
      <div className="run-controls"><div className="run-clock"><Clock3 size={15} /><span>{elapsed(state?.sim_time_s ?? 0)}</span></div>
        <button className="run-button start-button" disabled={busy || serviceUnavailable || scenarioPending || currentStatus === 'running' || scenarioCompleted || (currentStatus === 'paused' && dirty)} title={currentStatus === 'paused' && dirty ? 'Appliquez les modifications pour préparer un nouvel essai.' : undefined} onClick={() => void (currentStatus === 'paused' ? control('resume') : start())}><Play size={16} fill="currentColor" />{scenarioCompleted ? 'Terminé' : currentStatus === 'paused' ? 'Reprendre' : 'Démarrer'}</button>
        <button className="run-button" title="Mettre en pause" disabled={busy || serviceUnavailable || currentStatus !== 'running'} onClick={() => void control('pause')} aria-label="Mettre en pause"><Pause size={18} /></button>
        <button className="run-button stop-button" title="Arrêter l’essai" disabled={busy || serviceUnavailable || !['running', 'paused', 'error'].includes(currentStatus)} onClick={() => void control('stop')} aria-label="Arrêter l’essai"><Square size={15} fill="currentColor" /></button>
        <button className="run-button" title="Réinitialiser le modèle" disabled={busy || serviceUnavailable || currentStatus === 'running'} onClick={() => void control('reset')} aria-label="Réinitialiser le modèle"><RotateCcw size={17} /></button>
      </div>
    </header>

    <div className="projectbar"><div className="project-identity"><span className="project-icon"><FolderOpen size={22} /></span><div><input className="project-name" disabled={editorDisabled} aria-label="Nom du projet" value={project.name} onChange={event => onChange(project => ({ ...project, name: event.target.value }))} /><div className="project-subtitle"><span>{project.equipment.length} équipements</span><span>·</span><span>{project.tags.length} variables</span><span className={dirty ? 'unsaved-text' : 'saved-text'}>{dirty ? '• Modifications non enregistrées' : <><Check size={11} /> Enregistré</>}</span></div></div></div>
      <div className="project-actions"><button className="button ghost" aria-label="Nouveau" title="Nouveau projet" disabled={editorDisabled} onClick={() => { setNewName(''); setProjectsModal('new'); }}><FilePlus2 size={16} /><span>Nouveau</span></button><button className="button ghost" aria-label="Ouvrir" title="Ouvrir un projet" disabled={editorDisabled} onClick={() => void openProjects()}><FolderOpen size={16} /><span>Ouvrir</span></button><button className="button ghost" aria-label="Importer" title="Importer un projet" disabled={editorDisabled} onClick={() => fileInput.current?.click()}><Upload size={16} /><span>Importer</span></button><button className="button ghost" aria-label="Exporter" title="Exporter le projet" disabled={busy || serviceUnavailable || scenarioPending || (dirty && editorDisabled)} onClick={() => void exportProject()}><ArrowDownToLine size={16} /><span>Exporter</span></button><span className="toolbar-separator" /><button className="button save-button" disabled={editorDisabled || scenarioPending} onClick={() => void save()}><Save size={16} /><span>{currentStatus === 'paused' && dirty ? 'Appliquer en pause' : 'Enregistrer'}</span></button></div>
      <input ref={fileInput} type="file" accept=".json,application/json" hidden onChange={event => { const file = event.target.files?.[0]; if (file) void importFile(file); event.target.value = ''; }} />
      <input ref={archiveInput} type="file" aria-label="Archive FAT à restaurer" accept=".zip,application/zip" hidden onChange={event => { const file = event.target.files?.[0]; if (file) void importArchive(file); event.target.value = ''; }} />
    </div>

    <div className="tabsbar"><nav aria-label="Sections du banc FAT">{TABS.map(tab => <button key={tab.key} className={`tab-button ${activeTab === tab.key ? 'active' : ''}`} onClick={() => changeTab(tab.key)}><tab.icon size={16} /><span>{tab.label}</span>{tab.key === 'tags' && <small>{project.tags.length}</small>}</button>)}</nav><div className="runtime-status"><span className={`status-badge ${serviceUnavailable ? 'error' : currentStatus}`}><span />{projectConflict ? 'Autre projet actif' : networkError ? 'Service indisponible' : STATUS_LABELS[currentStatus]}</span><button className="icon-button" title="Guide de mise en service" onClick={() => changeTab('connection')} aria-label="Ouvrir le guide de mise en service"><CircleHelp size={18} /></button></div></div>

    {projectConflict && <div className="banner error-banner" role="alert"><CircleAlert size={18} /><span>Le projet actif a changé dans un autre onglet. Vos modifications restent dans cet onglet ; les commandes sont bloquées pour éviter toute action sur une autre cible.</span><div className="button-row"><button className="button compact-button" onClick={downloadDraft}>Télécharger mon brouillon</button>{scenarioDraft && <button className="button compact-button" onClick={() => downloadText(scenarioDraft.text, `${scenarioDraft.scenarioId}-etapes-brouillon.json`)}>Télécharger les étapes JSON</button>}<button className="button compact-button" onClick={() => { if (canReplace()) setBootAttempt(value => value + 1); }}>Recharger le projet actif</button></div></div>}
    {networkError && <div className="banner error-banner" role="alert"><CircleAlert size={18} /><span>Connexion au service local perdue. Les valeurs affichées sont anciennes. Vérifiez le serveur ; les commandes sont désactivées.</span></div>}
    {error && !projectsModal && !confirmTarget && <div className="banner error-banner" role="alert"><CircleAlert size={18} /><pre>{error}</pre><button className="icon-button" onClick={() => setError(null)} aria-label="Fermer le message d’erreur"><X size={16} /></button></div>}
    {state?.error && state.error !== error && <div className="banner error-banner" role="alert"><CircleAlert size={18} /><span>{state.error}</span></div>}
    {notice && <div className="toast" role="status"><Check size={17} />{notice}<button className="icon-button" onClick={() => setNotice('')} aria-label="Fermer la notification"><X size={15} /></button></div>}

    <main>
      {currentStatus === 'paused' && <div className="pause-edit-banner"><PencilRulerIcon /><span><strong>Essai en pause.</strong> Le P&ID est modifiable. {dirty ? 'Appliquez les modifications pour clore cet essai et en préparer un nouveau. Les preuves précédentes restent conservées.' : 'Reprendre continue cet essai. Enregistrer une modification prépare un nouvel essai.'}</span>{dirty && <button className="button compact-button" disabled={editorDisabled || scenarioPending} onClick={() => void save()}>Appliquer en pause</button>}</div>}
      {activeTab === 'pid' && <>
        <div className="workspace-toolbar"><div className="workspace-label"><span className="small-dot" /><strong>Vue procédé</strong><span>P&ID interactif</span></div><div className="workspace-actions"><div className="scenario-selector"><ListChecks size={15} /><label htmlFor="active-scenario">Scénario</label><select id="active-scenario" value={displayedScenarioId} disabled={editorDisabled} onChange={event => chooseScenario(event.target.value)}><option value="">Essai libre</option>{project.scenarios.map(scenario => <option key={scenario.id} value={scenario.id}>{scenario.name}</option>)}</select></div><button className="button presentation-toggle" aria-pressed={presentation} onClick={() => setPresentation(value => !value)}>{presentation ? <Minimize2 size={14} /> : <Maximize2 size={14} />}{presentation ? 'Quitter la présentation' : 'Mode présentation'}</button></div></div>
        <PidCanvas {...props} catalog={catalog} key={project.id} scenario={activeScenario} viewRequest={viewRequest} presentation={presentation && currentStatus !== 'paused'} />
        <ScenarioRun project={project} state={dirty ? null : state} scenario={activeScenario} online={props.online && !dirty} onSnapshot={receiveSnapshot} onError={setError} observations={guidedObservations} onObservationChange={(key, text) => setGuidedObservations(current => ({ ...current, [key]: text }))} onPrepare={() => { setViewRequest(value => value + 1); setShowLivePanel(true); }} />
        <div className="live-panel-heading"><button onClick={() => setShowLivePanel(value => !value)}><Activity size={16} />Acquisition de l’essai<ChevronDown size={15} className={showLivePanel ? 'rotate-180' : ''} /></button><div>{totalForces > 0 && <span className="forced-counter">{totalForces} forçage{totalForces > 1 ? 's' : ''}</span>}{totalFaults > 0 && <span className="fault-counter">{totalFaults} défaut{totalFaults > 1 ? 's' : ''}</span>}<button className="text-link" onClick={() => changeTab('trends')}>Ouvrir tendances & rapport →</button></div></div>
        {showLivePanel && <div className="live-overview"><div><TrendChart project={project} state={state} compact preferredTags={activeScenario?.trend_tags} /></div><div className="live-events"><div className="live-events-title">Derniers événements</div>{(state?.events ?? []).slice(-4).reverse().map(event => <div key={event.id}><time>{fmt(event.sim_time_s)} s</time><p>{event.message}</p></div>)}{!state?.events.length && <p className="small-muted">Démarrez l’essai pour suivre les actions et les diagnostics.</p>}</div></div>}
      </>}
      {activeTab === 'tags' && <VariablesPanel {...props} onImport={importMapping} onExport={exportMapping} />}
      {activeTab === 'scenarios' && <ScenariosPanel {...props} key={`${project.id}:${scenarioPanelVersion}`} selectedId={displayedScenarioId} onSelect={chooseScenario} onDraftChange={setScenarioDraft} onExport={exportScenarios} onImport={importScenarios} pending={scenarioPending} />}
      {activeTab === 'trends' && <TrendsPanel {...props} draft={reportDraft} onDraftChange={changeReportDraft} />}
      {activeTab === 'connection' && <ConnectionPanel {...props} validation={validation} onValidate={validate} catalog={catalog} />}
    </main>

    <footer className="statusbar"><div><span className={`small-dot ${state?.connection.connected && !serviceUnavailable ? 'green' : ''}`} /><strong>{project.plc.mode === 'demo' ? 'Contrôleur de démonstration' : 'OPC UA · ' + (state?.connection.connected ? 'connecté' : 'déconnecté')}</strong><span className="footer-divider" /><span>{project.plc.mode === 'demo' ? 'Aucun automate raccordé' : state?.connection.target || project.plc.endpoint}</span></div><div><span>Pas : {project.simulation.step_ms} ms</span><span>Vitesse : ×{project.simulation.speed}</span><span>{fmt(state?.write_count ?? 0, 0)} écritures</span><Network size={13} /><span>Local · 127.0.0.1</span></div></footer>

    {projectsModal && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="projects-modal-title"><div className="modal-heading"><h2 id="projects-modal-title">{projectsModal === 'new' ? 'Nouveau projet FAT' : 'Ouvrir un projet'}</h2><button className="icon-button" onClick={() => setProjectsModal(null)} aria-label="Fermer la fenêtre"><X size={19} /></button></div>
      {error && <DialogError message={error} onClose={() => setError(null)} />}
      {projectsModal === 'new' ? <form onSubmit={event => { event.preventDefault(); void newProject(); }}><label>Nom du projet<input autoFocus value={newName} onChange={event => setNewName(event.target.value)} placeholder="Ex. Skid de dosage — FAT 01" maxLength={120} required /></label><p className="small-muted">Le projet commence avec un canevas vide et le mode démonstration local.</p><div className="modal-actions"><button type="button" className="button" onClick={() => setProjectsModal(null)}>Annuler</button><button className="button primary" disabled={busy || !newName.trim()}><PlusIcon />Créer le projet</button></div></form>
        : <><div className="demo-project public-demo-project"><div><strong>Laboratoire · Transfert de liquides</strong><p>Trois cuves, quatre pompes, huit vannes et instruments. Demandes manuelles, retours physiques et FAT préparées, sans séquence métier imposée.</p></div><button className="button primary" disabled={busy} onClick={() => void loadPilot()}>Charger le laboratoire</button></div><div className="archive-actions"><strong>Archiver le projet complet</strong><p>L’archive .fat.zip contient le P&ID, les variables, les animations, les scénarios, le mapping et l’historique de ce projet. Enregistrez-la dans le dossier de votre choix.</p><div className="button-row"><button className="button" disabled={busy || scenarioPending} onClick={() => void exportArchive()}><ArrowDownToLine size={15} />Exporter l’archive FAT</button><button className="button" disabled={busy || scenarioPending} onClick={() => archiveInput.current?.click()}><Upload size={15} />Restaurer une archive FAT</button></div><p>La restauration crée un nouveau dossier local et l’ouvre au repos. L’ancien espace reste disponible. Les secrets et autorisations du poste ne sont pas importés.</p></div><div className="workspace-list"><h3>Dossiers FAT locaux</h3>{workspaces.map(workspace => <div className="workspace-item" data-workspace={workspace.id} key={workspace.id}><FolderOpen size={17} /><div><strong>{workspace.name}</strong><small>{workspace.path}</small>{workspace.error && <small className="failed-text">{workspace.error}</small>}</div><button className="button compact-button" disabled={busy || workspace.active || Boolean(workspace.error)} onClick={() => void openWorkspace(workspace.id)} aria-label={`Ouvrir le dossier ${workspace.name}`}>{workspace.active ? 'Actif' : 'Ouvrir'}</button></div>)}</div><h3 className="saved-projects-title">Projets de l’espace actif</h3><div className="project-list">{projects.map(entry => <button key={entry.id} onClick={() => void loadProject(entry.id)} disabled={busy}><FolderOpen size={20} /><span><strong>{entry.name}</strong><small>{entry.updated_at ? new Date(entry.updated_at).toLocaleString('fr-CH') : entry.id}</small></span>{entry.id === project.id && <span className="type-label">Ouvert</span>}</button>)}{!projects.length && <p className="empty-inline">Aucun projet enregistré.</p>}</div><div className="demo-project"><div><strong>Exemple TK-101</strong><p>Cuve, pompe, vannes et trois scénarios de référence.</p></div><button className="button" disabled={busy} onClick={() => void loadDemo()}>Charger la démo</button></div><p className="small-muted">Les projets s’exportent en JSON versionné 1.0. L’import accepte aussi les anciens fichiers de projet.</p></>}
    </section></div>}

    {confirmTarget && <div className="modal-backdrop"><section className="modal target-modal" role="dialog" aria-modal="true" aria-labelledby="target-title"><div className="modal-heading"><h2 id="target-title">Confirmer la cible virtuelle</h2><button className="icon-button" onClick={() => setConfirmTarget(false)} aria-label="Annuler la connexion"><X size={18} /></button></div>{error && <DialogError message={error} onClose={() => setError(null)} />}<div className="target-identity"><span>INSTANCE APPROUVÉE</span><strong>{project.plc.approved_virtual_target || 'Nom non renseigné'}</strong><code>{expectedTarget}</code><small>{project.plc.expected_application_uri}</small></div><p>Le banc va lire les commandes PLC et écrire uniquement les entrées simulées autorisées. Vérifiez que cette cible appartient à l’instance PLCSIM Advanced de votre poste.</p><label>Recopiez exactement la cible pour confirmer<input autoFocus className="mono" value={targetText} onChange={event => setTargetText(event.target.value)} placeholder={expectedTarget} /></label><div className="modal-actions"><button className="button" onClick={() => setConfirmTarget(false)}>Annuler</button><button className="button primary" disabled={busy || targetText !== expectedTarget} onClick={() => void start(targetText)}><Shield size={16} />Connecter et démarrer</button></div></section></div>}
  </div>;
}

function PlusIcon() { return <FilePlus2 size={16} />; }
function PencilRulerIcon() { return <Settings2 size={17} />; }
function DialogError({ message, onClose }: { message: string; onClose: () => void }) { return <div className="inline-error dialog-error" role="alert"><CircleAlert size={17} /><pre>{message}</pre><button type="button" className="icon-button" aria-label="Fermer le message d’erreur" onClick={onClose}><X size={15} /></button></div>; }
