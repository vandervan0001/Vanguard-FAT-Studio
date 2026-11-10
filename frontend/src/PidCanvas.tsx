import { memo, useCallback, useEffect, useId, useMemo, useRef, useState, type CSSProperties } from 'react';
import {
  ReactFlow, ReactFlowProvider, Background, BackgroundVariant, Controls, MiniMap,
  Handle, Position, MarkerType, useReactFlow, BaseEdge, getSmoothStepPath,
  type Node, type NodeProps, type NodeChange, type EdgeChange, type Connection, type EdgeProps,
} from '@xyflow/react';
import { CircleHelp, Copy, GripVertical, Plus, Route, Search, Trash2, Unlink, WandSparkles, X, Zap, RotateCcw, PencilRuler, Radio, Link2 } from 'lucide-react';
import { api } from './api';
import { fmt, uid, type CatalogItem, type Equipment, type EquipmentType, type Project, type Snapshot, type Tag, type Scenario } from './types';
import { DigitalInputs, AnalogInputs, PlcOutputs } from './TestConsole';
import { ForceField } from './ForceField';
import { scenarioFocus } from './ScenarioRun';
import { AnimationEditor, animationReading } from './AnimationEditor';
import { diagnosticLabel, diagnosticProfile, displayValue, engineeringUnit } from './signal';
import { BindingEditor } from './BindingEditor';
import { compatibleTag, fillCircuit, freePosition, makeEquipment, missingPortTags } from './pidBuilder';
import { TransferBuilder } from './TransferBuilder';
import { FlowExplanation } from './FlowExplanation';
import { CircuitLibrary } from './CircuitLibraryDialog';
import { isFlowEquipment } from './processCircuits';

type Props = {
  project: Project; state: Snapshot | null; catalog: CatalogItem[]; locked: boolean; online: boolean;
  onChange: (update: (project: Project) => Project) => void;
  onError: (message: string) => void; onSnapshot: (state: Snapshot) => void;
  scenario?: Scenario | null; viewRequest?: number; presentation?: boolean; unavailable?: string; modelDirty?: boolean;
  focusRequest?: { equipmentId?: string; port?: string; field?: string; nonce: number };
};
type EquipmentNode = Node<{ equipment: Equipment; state: Record<string, unknown>; tags: Snapshot['tags']; faults: Record<string, unknown>; locked: boolean; operating: boolean; highlighted?: boolean; signalTag?: Tag; animationDataType?: Tag['data_type'] }, 'equipment'>;

const TYPE_LABELS: Record<EquipmentType, string> = { tank: 'Cuve', pump: 'Pompe', pump_vfd: 'Pompe à variateur', valve_onoff: 'Vanne TOR', valve_control: 'Vanne modulante', analog_sensor: 'Capteur analogique', digital_sensor: 'Capteur binaire', digital_input: 'Bouton / entrée TOR', indicator: 'Indicateur' };
const FAULTS: Partial<Record<EquipmentType, { key: string; label: string }[]>> = {
  pump: [{ key: 'motor_trip', label: 'Défaut moteur' }],
  pump_vfd: [{ key: 'motor_trip', label: 'Défaut moteur' }],
  valve_onoff: [{ key: 'valve_stuck', label: 'Vanne bloquée' }],
  valve_control: [{ key: 'valve_stuck', label: 'Vanne bloquée' }],
  analog_sensor: [{ key: 'sensor_stuck', label: 'Capteur figé' }, { key: 'out_of_range', label: 'Signal hors plage' }],
  digital_sensor: [{ key: 'sensor_stuck', label: 'Capteur figé' }],
};

export function ProcessSymbol({ type, active = false, level = 40, compact = false, label }: { type: EquipmentType; active?: boolean; level?: number; compact?: boolean; label?: string }) {
  const fillId = useId().replace(/:/g, '');
  const stroke = active ? 'var(--symbol-active, #078a75)' : 'var(--symbol-inactive, #607a8d)';
  const clampedLevel = Math.min(100, Math.max(0, level));
  return <svg className={`process-symbol ${compact ? 'compact' : ''}`} viewBox="0 0 100 85" fill="none" aria-hidden="true">
    <defs><linearGradient id={`${fillId}-shell`} x1="0" x2="1"><stop stopColor="#dce8ee" /><stop offset=".35" stopColor="#ffffff" /><stop offset="1" stopColor="#e2edf1" /></linearGradient></defs>
    {type === 'tank' ? <>
      <path d="M24 14 Q50 1 76 14 V67 Q50 80 24 67 Z" fill={`url(#${fillId}-shell)`} stroke={stroke} strokeWidth="2" />
      <svg x="25.5" y="13" width="49" height="57" viewBox="0 0 49 57" overflow="hidden">
        <rect className="tank-liquid" x="0" y={57 - clampedLevel * .57} width="49" height={clampedLevel * .57} fill="#a2dcce" />
        <path d={`M0 ${57 - clampedLevel * .57} Q12 ${53 - clampedLevel * .57} 24 ${57 - clampedLevel * .57} T49 ${57 - clampedLevel * .57}`} stroke="#0b9b86" strokeWidth="1.8" />
      </svg>
      <path d="M24 14 Q50 27 76 14 M24 67 Q50 80 76 67 M24 42 H7 M76 57 H93 M34 74 V81 M66 74 V81 M50 8 V1" stroke={stroke} strokeWidth="2" />
      <path d="M50 74 V84 M20 81 H40 M60 81 H80" stroke={stroke} strokeWidth="2" />
      {[25, 34, 43, 52, 61].map(y => <path key={y} d={`M69 ${y} H74`} stroke="#6a938f" />)}
    </> : type === 'pump' || type === 'pump_vfd' ? <>
      <path d="M4 43 H29 M72 43 H96 M39 65 L32 76 H69 L61 65" stroke={stroke} strokeWidth="3" strokeLinejoin="round" />
      <circle cx="50" cy="43" r="23" fill={`url(#${fillId}-shell)`} stroke={stroke} strokeWidth="2" />
      {type === 'pump_vfd' && <text x="50" y="13" textAnchor="middle" fill={stroke} fontSize="10">VFD</text>}
      <g className="rotating-part"><path d="M50 24 C64 24 67 34 50 43 C65 49 65 61 50 62 C36 61 33 50 50 43 C34 36 36 25 50 24 Z" fill={stroke} fillOpacity=".8" /><circle cx="50" cy="43" r="4" fill="#f6fafb" stroke={stroke} strokeWidth="1.5" /></g>
    </> : type === 'valve_onoff' || type === 'valve_control' ? <>
      <path d="M4 52 H24 M76 52 H96 M50 50 V22" stroke={stroke} strokeWidth="2.5" />
      <path d="M24 36 L76 68 V36 L24 68 Z" fill={active ? '#d2f1e7' : '#f7fafc'} stroke={stroke} strokeWidth="2.5" strokeLinejoin="round" />
      {type === 'valve_control' ? <><path d="M33 23 A17 13 0 0 1 67 23 Z" fill="#e7f0f4" stroke={stroke} strokeWidth="2" /><path d="M38 17 H62" stroke={stroke} strokeWidth="1.5" /><path d={`M${38 + clampedLevel * .24} 13 V21`} stroke={stroke} strokeWidth="3" /></> : <><rect x="38" y="11" width="24" height="16" rx="2" fill="#e7f0f4" stroke={stroke} strokeWidth="2" /><path d="M38 27 L62 11" stroke={stroke} strokeWidth="1.3" /></>}
    </> : type === 'digital_input' ? <>
      <path d="M7 57 H30 M70 57 H93 M32 55 L66 39 M37 15 H63 M50 15 V41 M38 43 H62" stroke={stroke} strokeWidth="2.5" strokeLinecap="round" />
      <circle cx="31" cy="57" r="3" fill="#fff" stroke={stroke} strokeWidth="2" /><circle cx="69" cy="57" r="3" fill="#fff" stroke={stroke} strokeWidth="2" />
      <path d="M46 25 H54 M46 30 H54" stroke={stroke} strokeWidth="1.5" />
    </> : <>
      <path d="M50 64 V81" stroke={stroke} strokeWidth="2" strokeDasharray={type === 'indicator' ? '3 3' : undefined} />
      <circle cx="50" cy="39" r="25" fill={active ? '#e4f5ef' : '#f7fafc'} stroke={stroke} strokeWidth="2.5" />
      <path d="M26 39 H74" stroke={stroke} strokeWidth="1.5" />
      <text x="50" y="33" textAnchor="middle" fill={stroke} fontSize="12" fontWeight="650">{label?.match(/^[A-Za-z]+/)?.[0] ?? (type === 'analog_sensor' ? 'AI' : type === 'digital_sensor' ? 'DI' : 'ST')}</text>
      <text x="50" y="55" textAnchor="middle" fill={stroke} fontSize="11">{label?.match(/\d+/)?.[0] ?? (type === 'analog_sensor' ? 'ANA' : type === 'digital_sensor' ? '0 / 1' : 'PLC')}</text>
    </>}
  </svg>;
}

const SymbolNode = memo(function SymbolNode({ data, selected }: NodeProps<EquipmentNode>) {
  const { equipment, state, tags, faults } = data;
  const primaryPort = equipment.type === 'tank' ? 'level' : equipment.type === 'pump_vfd' ? 'speed' : equipment.type === 'pump' ? 'feedback' : equipment.type.startsWith('valve') ? 'position' : 'value';
  const portValue = tags[equipment.bindings[primaryPort]]?.value;
  const value = equipment.type === 'tank' ? state.level_percent ?? state.level ?? portValue : portValue ?? state[equipment.type === 'pump' ? 'running' : primaryPort] ?? state.value;
  const physicalValue = equipment.type.startsWith('valve') ? state.position ?? value : state.running ?? value;
  const visual = equipment.animation ? animationReading(equipment.animation, tags[equipment.animation.tag_id], data.animationDataType) : null;
  const badBinding = Object.values(equipment.bindings).some(id => /bad|stale|error|disconnected/i.test(tags[id]?.quality ?? ''));
  const unavailable = badBinding || Boolean(visual && !visual.available && !visual.initial);
  const active = !unavailable && (visual ? visual.active : typeof physicalValue === 'boolean' ? physicalValue : typeof physicalValue === 'number' && physicalValue > 0);
  const faulted = Object.keys(faults).length > 0 || Boolean(state.fault);
  const forced = Object.values(equipment.bindings).some(id => tags[id]?.forced);
  const scaledTag = equipment.type === 'analog_sensor' && data.signalTag?.signal ? data.signalTag : null;
  const profile = scaledTag ? diagnosticProfile(scaledTag, tags[scaledTag.id]) : null;
  const reading = unavailable || value === undefined ? undefined : profile ? diagnosticLabel(profile) : visual?.available && ['level', 'position'].includes(equipment.animation?.effect ?? '') ? visual.percent : scaledTag ? displayValue(scaledTag, value as number, 'engineering') : value;
  const unit = scaledTag ? engineeringUnit(scaledTag) : primaryPort === 'level' || primaryPort === 'position' || primaryPort === 'speed' ? '%' : equipment.unit;
  const level = unavailable ? 0 : visual?.available && ['level', 'position'].includes(equipment.animation?.effect ?? '') ? visual.percent : Number(state.level_percent ?? state.level ?? state.position ?? value ?? equipment.params.initial_level_pct ?? 0);
  const style = { '--symbol-active': equipment.animation?.active_color ?? '#078f79', '--symbol-inactive': unavailable ? '#b47b60' : equipment.animation?.inactive_color ?? '#607a8d' } as CSSProperties;
  const animationClass = !unavailable && visual?.available && visual.active ? `animation-${equipment.animation?.effect}` : '';
  return <div className={`equipment-node type-${equipment.type} ${equipment.type === 'tank' ? 'tank-node' : ''} ${selected ? 'selected' : ''} ${faulted ? 'faulted' : ''} ${unavailable ? 'quality-unavailable' : ''} ${forced ? 'forced-node' : ''} ${data.highlighted ? 'fat-focus' : ''} ${animationClass}`} style={style} data-animation-active={visual ? String(!unavailable && visual.available && visual.active) : undefined} data-animation-quality={visual ? unavailable ? 'unavailable' : visual.available ? 'available' : 'initial' : undefined} title={equipment.description || equipment.name}>
    <Handle type="target" position={Position.Left} isConnectable={!data.locked} />
    {data.operating && [Position.Left, Position.Right, Position.Top, Position.Bottom].flatMap(position => ['source', 'target'].map(type => <Handle key={`${type}-${position}`} id={`${type}-${position}`} className="routing-handle" type={type as 'source' | 'target'} position={position} isConnectable={false} />))}
    <div className="node-label"><span>{equipment.name.split(' · ')[0]}</span>{unavailable ? <span className="node-alert">QUALITÉ</span> : faulted ? <span className="node-alert">DÉFAUT</span> : forced ? <span className="node-force">FORCÉ</span> : null}</div>
    <div className="node-description">{equipment.name.includes(' · ') ? equipment.name.split(' · ').slice(1).join(' · ') : TYPE_LABELS[equipment.type]}</div>
    <ProcessSymbol type={equipment.type} active={active} level={level} label={equipment.name.split(' · ')[0]} />
    <div className={`node-value ${active ? 'is-active' : ''}`}>{unavailable ? 'Indisponible' : reading === undefined ? TYPE_LABELS[equipment.type] : `${fmt(reading)}${typeof reading === 'number' && unit ? ' ' + unit : ''}`}</div>
    <Handle type="source" position={Position.Right} isConnectable={!data.locked} />
  </div>;
});
const nodeTypes = { equipment: SymbolNode };

function ProcessPipe(props: EdgeProps) {
  const [path, labelX, labelY] = getSmoothStepPath({ sourceX: props.sourceX, sourceY: props.sourceY, targetX: props.targetX, targetY: props.targetY, sourcePosition: props.sourcePosition, targetPosition: props.targetPosition, borderRadius: 14, offset: 28 });
  const instrument = props.data?.instrument;
  return <><BaseEdge id={props.id} path={path} markerEnd={props.markerEnd} label={props.label} labelX={labelX} labelY={labelY} labelStyle={props.labelStyle} labelBgStyle={props.labelBgStyle} style={{ ...props.style, strokeWidth: instrument ? 1.5 : 5, strokeDasharray: instrument ? '5 5' : undefined }} /><path d={path} data-edge-id={props.id} data-flowing={String(Boolean(props.data?.flowing))} className={`pipe-core ${props.data?.flowing ? 'flowing' : ''}`} fill="none" stroke={instrument ? 'none' : '#d3e4e7'} strokeWidth="2" pointerEvents="none" /></>;
}
const edgeTypes = { process: ProcessPipe };

function Canvas({ project, state, catalog, locked, online, unavailable, onChange, onError, onSnapshot, scenario, viewRequest, presentation, focusRequest, modelDirty }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [snapToGrid, setSnapToGrid] = useState(true);
  const [building, setBuilding] = useState(!project.equipment.length);
  const [showConsoles, setShowConsoles] = useState(false);
  const [librarySearch, setLibrarySearch] = useState('');
  const [fitAdded, setFitAdded] = useState(false);
  const [circuitMode, setCircuitMode] = useState<'template' | 'transfer' | null>(null);
  const [flowOpen, setFlowOpen] = useState(false);
  const [savedCircuitsOpen, setSavedCircuitsOpen] = useState(false);
  const [inspectorFocus, setInspectorFocus] = useState<Props['focusRequest']>();
  const [measurements, setMeasurements] = useState<Record<string, { width: number; height: number }>>({});
  const canvasRef = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition, fitView } = useReactFlow();
  useEffect(() => {
    if (!focusRequest) return;
    setBuilding(true); setSelectedEdge(null); setSelectedId(focusRequest.equipmentId ?? null); setInspectorFocus(focusRequest);
    const timer = setTimeout(() => { if (focusRequest.equipmentId) void fitView({ nodes: [{ id: focusRequest.equipmentId }], padding: .8, maxZoom: 1, duration: 200 }); }, 120);
    return () => clearTimeout(timer);
  }, [focusRequest?.nonce, fitView]);
  useEffect(() => {
    if (!fitAdded) return;
    const timer = setTimeout(() => { void fitView({ padding: .2, maxZoom: 1, duration: 200 }); setFitAdded(false); }, 90);
    return () => clearTimeout(timer);
  }, [fitAdded, project.equipment.length, fitView]);
  const focusedIds = useMemo(() => scenario ? scenarioFocus(project, scenario) : [], [project, scenario]);
  useEffect(() => { if (state?.status === 'running') setBuilding(false); else if (state?.status === 'paused') setBuilding(true); }, [state?.status]);
  useEffect(() => {
    const timer = setTimeout(() => void fitView({ nodes: focusedIds.length ? focusedIds.map(id => ({ id })) : undefined, padding: .2, duration: 250 }), 90);
    return () => clearTimeout(timer);
  }, [scenario?.id, viewRequest, building, presentation, showConsoles, fitView]);
  useEffect(() => {
    if (!canvasRef.current) return;
    let timer: ReturnType<typeof setTimeout>;
    const observer = new ResizeObserver(() => { clearTimeout(timer); timer = setTimeout(() => void fitView({ padding: .12, duration: 150 }), 160); });
    observer.observe(canvasRef.current);
    return () => { clearTimeout(timer); observer.disconnect(); };
  }, [fitView]);
  const selected = project.equipment.find(equipment => equipment.id === selectedId);
  const visibleEquipment = useMemo(() => project.equipment.filter(item => building || !['digital_input', 'indicator'].includes(item.type)), [project.equipment, building]);
  const nodes = useMemo<EquipmentNode[]>(() => visibleEquipment.map(equipment => ({
    id: equipment.id, type: 'equipment', position: equipment.position, measured: measurements[equipment.id], selected: selectedId === equipment.id,
    data: { equipment, state: state?.equipment[equipment.id] ?? {}, tags: state?.tags ?? {}, faults: state?.faults[equipment.id] ?? {}, locked: locked || !building, operating: !building, highlighted: focusedIds.includes(equipment.id), signalTag: project.tags.find(tag => tag.id === equipment.bindings.value), animationDataType: project.tags.find(tag => tag.id === equipment.animation?.tag_id)?.data_type },
  })), [visibleEquipment, state?.equipment, state?.tags, state?.faults, selectedId, locked, building, focusedIds, measurements, project.tags]);
  const edges = useMemo(() => project.connections.filter(connection => visibleEquipment.some(item => item.id === connection.source) && visibleEquipment.some(item => item.id === connection.target)).map(connection => {
    const source = visibleEquipment.find(item => item.id === connection.source)!;
    const target = visibleEquipment.find(item => item.id === connection.target)!;
    const dx = target.position.x - source.position.x;
    const dy = target.position.y - source.position.y;
    const vertical = Math.abs(dy) > Math.abs(dx) * .8;
    const from = vertical ? dy >= 0 ? 'bottom' : 'top' : dx >= 0 ? 'right' : 'left';
    const to = vertical ? dy >= 0 ? 'top' : 'bottom' : dx >= 0 ? 'left' : 'right';
    const instrument = ['analog_sensor', 'digital_sensor', 'digital_input', 'indicator'].some(type => [source.type, target.type].includes(type as EquipmentType));
    const unavailable = state?.status !== 'idle' && (/bad|stale|error|disconnected/i.test(state?.connection.quality ?? '') || [source, target].some(item => Object.values(item.bindings).some(id => /bad|stale|error|disconnected/i.test(state?.tags[id]?.quality ?? ''))));
    const flows = [connection.source, connection.target].map(id => state?.equipment[id]?.flow_l_s).filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
    const flowing = !instrument && !unavailable && state?.status === 'running' && flows.length > 0 && Math.min(...flows) > .001;
    return { ...connection, type: 'process', selected: selectedEdge === connection.id, ...(!building ? { sourceHandle: `source-${from}`, targetHandle: `target-${to}` } : {}), data: { instrument, flowing },
      style: { stroke: selectedEdge === connection.id ? '#dd8a4c' : unavailable ? '#bf9878' : instrument ? '#9baeb8' : flowing ? '#1a9b87' : '#668d99' },
      ...(connection.directed && !instrument ? { markerEnd: { type: MarkerType.ArrowClosed, color: flowing ? '#15917f' : '#668d99', width: 14, height: 14 } } : {}),
      labelStyle: { fill: '#527080', fontSize: 11 }, labelBgStyle: { fill: '#f5f9fa', fillOpacity: .96 },
    };
  }), [project.connections, visibleEquipment, selectedEdge, state?.status, state?.equipment, state?.tags, state?.connection.quality, building]);

  const addEquipment = (type: EquipmentType, position?: { x: number; y: number }) => {
    if (locked || !building) return;
    if (project.equipment.length >= 50) { onError('Le projet est limité à 50 équipements.'); return; }
    const item = catalog.find(item => item.type === type);
    if (!item) return;
    const bounds = canvasRef.current?.getBoundingClientRect();
    const centre = screenToFlowPosition({ x: bounds ? bounds.x + bounds.width / 2 : window.innerWidth / 2, y: bounds ? bounds.y + bounds.height / 2 : window.innerHeight / 2 });
    const equipment = makeEquipment(item, project.equipment, position ?? freePosition(project.equipment, { x: centre.x - 75, y: centre.y - 90 }));
    onChange(project => ({ ...project, equipment: [...project.equipment, equipment] }));
    setSelectedId(equipment.id); setSelectedEdge(null); if (!position) setFitAdded(true);
  };

  const onNodesChange = useCallback((changes: NodeChange<EquipmentNode>[]) => {
    const resized = changes.filter(change => change.type === 'dimensions' && change.dimensions);
    if (resized.length) setMeasurements(current => {
      const next = { ...current };
      let changed = false;
      for (const change of resized) {
        if (change.type === 'dimensions' && change.dimensions && (current[change.id]?.width !== change.dimensions.width || current[change.id]?.height !== change.dimensions.height)) {
          next[change.id] = change.dimensions; changed = true;
        }
      }
      return changed ? next : current;
    });
    const selection = changes.find(change => change.type === 'select' && change.selected);
    if (selection && selection.type === 'select') { setSelectedId(selection.id); setSelectedEdge(null); }
    if (locked) return;
    const positions = changes.filter(change => change.type === 'position' && change.position);
    const removed = changes.filter(change => change.type === 'remove').map(change => change.id);
    if (!positions.length && !removed.length) return;
    onChange(project => ({ ...project,
      equipment: project.equipment.filter(equipment => !removed.includes(equipment.id)).map(equipment => {
        const change = positions.find(change => 'id' in change && change.id === equipment.id);
        return change?.type === 'position' && change.position ? { ...equipment, position: change.position } : equipment;
      }),
      connections: project.connections.filter(connection => !removed.includes(connection.source) && !removed.includes(connection.target)),
    }));
  }, [locked, onChange]);

  const onEdgesChange = (changes: EdgeChange[]) => {
    const selection = changes.find(change => change.type === 'select' && change.selected);
    if (selection?.type === 'select') { setSelectedEdge(selection.id); setSelectedId(null); }
    if (locked) return;
    const removed = changes.filter(change => change.type === 'remove').map(change => change.id);
    if (removed.length) onChange(project => ({ ...project, connections: project.connections.filter(connection => !removed.includes(connection.id)) }));
  };

  const onConnect = (connection: Connection) => {
    if (locked || !connection.source || !connection.target || connection.source === connection.target) return;
    if (project.connections.some(edge => edge.source === connection.source && edge.target === connection.target)) return;
    if (project.connections.length >= 200) { onError('Le projet est limité à 200 liaisons.'); return; }
    onChange(project => ({ ...project, connections: [...project.connections, { id: uid('line'), source: connection.source, target: connection.target, label: '', directed: true }] }));
  };

  const controls = { project, state, unavailable, onError, onSnapshot };
  const inspector = selected || selectedEdge || building ? <aside className="inspector panel">
    {selected ? <Inspector key={selected.id} equipment={selected} project={project} state={state} catalog={catalog} locked={locked || !building} online={online} unavailable={unavailable} onChange={onChange} onError={onError} onSnapshot={onSnapshot} focusRequest={inspectorFocus?.equipmentId === selected.id ? inspectorFocus : undefined} showForces={building} onCopied={ids => { setSelectedId(ids[0] ?? null); setFitAdded(true); setInspectorFocus(undefined); }} onClose={() => setSelectedId(null)} />
      : selectedEdge ? <ConnectionInspector project={project} id={selectedEdge} locked={locked || !building} onChange={onChange} onClose={() => setSelectedEdge(null)} />
        : <><div className="panel-title">Propriétés</div><div className="inspector-empty"><ProcessSymbol type="tank" /><h3>Sélectionnez un équipement</h3><p>Ses paramètres, ses variables PLC et ses défauts de simulation apparaîtront ici.</p></div><div className="model-note"><strong>Débits et liaisons</strong><p>Les conduites sont graphiques. Le débit est défini par la cuve cible, le sens et le groupe de débit de chaque pompe ou vanne.</p><p>Dans un même groupe, l’équipement le plus limitant fixe le débit. Les groupes indépendants s’additionnent.</p></div></>}
  </aside> : null;
  return <div className={`workbench ${building ? 'building-mode' : 'operating-mode'} ${presentation && !building ? 'presented-workbench' : ''} ${presentation && !showConsoles && !building ? 'consoles-hidden' : ''}`}>
    {building ? <aside className="palette panel">
      <div className="panel-title">Bibliothèque <span className="subtle-count">{String(catalog.length).padStart(2, '0')}</span></div>
      <p className="panel-hint">Cliquez pour ajouter, ou glissez à l’endroit voulu.</p>
      {!project.equipment.length && <div className="pid-starter"><strong>Partir d’un circuit</strong><p>Cuve, pompe, vanne, conduites et tags locaux prêts à modifier.</p><button className="button primary compact-button" disabled={locked} onClick={() => {
        try { const next = fillCircuit(project, catalog); onChange(current => current === project ? next : current); setSelectedId(next.equipment.find(item => item.type === 'pump')!.id); setFitAdded(true); }
        catch (error) { onError(error instanceof Error ? error.message : String(error)); }
      }}>Insérer un circuit de remplissage</button></div>}
      <div className="circuit-launch"><button className="button compact-button" disabled={locked} onClick={() => setCircuitMode('template')}><Route size={15} />Circuits et transferts</button><button className="button compact-button" disabled={locked} onClick={() => setSavedCircuitsOpen(true)}>Mes circuits</button></div>
      <label className="palette-search"><Search size={14} /><input aria-label="Rechercher un équipement" placeholder="Cuve, pompe, capteur…" value={librarySearch} onChange={event => setLibrarySearch(event.target.value)} /></label>
      <div className="palette-items">
        {catalog.filter(item => `${item.label} ${item.description}`.toLocaleLowerCase().includes(librarySearch.trim().toLocaleLowerCase())).map(item => <button key={item.type} className="palette-item" draggable={!locked && project.equipment.length < 50} disabled={locked || project.equipment.length >= 50}
          onDragStart={event => { event.dataTransfer.setData('application/fat-equipment', item.type); event.dataTransfer.effectAllowed = 'move'; }}
          onClick={() => addEquipment(item.type)} title={`${item.description}\nCliquer ou glisser pour ajouter`}>
          <ProcessSymbol type={item.type} compact /><span>{item.label}</span><GripVertical size={13} className="drag-hint" />
        </button>)}
      </div>
      <div className="palette-note"><CircleHelp size={15} /><p>Reliez les points latéraux, ou choisissez « Relier à » dans les propriétés.</p></div>
      <label className="check-label grid-choice"><input type="checkbox" checked={snapToGrid} onChange={event => setSnapToGrid(event.target.checked)} />Aligner sur la grille</label>
      <div className="keyboard-help"><kbd>Suppr</kbd> supprimer<br /><kbd>Molette</kbd> zoomer<br /><kbd>Glisser fond</kbd> déplacer</div>
    </aside> : <DigitalInputs {...controls} />}

    <div ref={canvasRef} className="canvas-area" onDragOver={event => { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; }}
      onDrop={event => { event.preventDefault(); const type = event.dataTransfer.getData('application/fat-equipment') as EquipmentType; if (catalog.some(item => item.type === type)) addEquipment(type, screenToFlowPosition({ x: event.clientX, y: event.clientY })); }}>
      <div className="canvas-topline"><span><span className={`small-dot ${state?.status === 'running' ? 'green' : ''}`} />{building ? 'CONSTRUCTION DU PROCÉDÉ' : project.name.toLocaleUpperCase('fr-CH')}</span><div>{presentation && !building && <button aria-pressed={showConsoles} onClick={() => setShowConsoles(value => !value)}>{showConsoles ? 'Masquer les pupitres' : 'Afficher les pupitres'}</button>}<button className="canvas-mode" disabled={locked} onClick={() => { setBuilding(value => !value); setSelectedId(null); setSelectedEdge(null); }}>{building ? <Radio size={12} /> : <PencilRuler size={12} />}{building ? 'Tester les I/O' : 'Construire'}</button><button onClick={() => setFlowOpen(true)}>Expliquer les débits</button><button onClick={() => fitView({ padding: .12, duration: 200 })}>Vue complète</button></div></div>
      {locked && <div className="editing-locked">{!online ? 'Service indisponible · commandes désactivées' : state?.guided_steps?.at(-1)?.state === 'queued' ? 'STEP en attente du cycle d’échange · I/O temporairement suspendues' : state?.status === 'paused' ? 'Essai en pause · structure figée · reprendre pour les impulsions' : state?.status === 'running' ? 'I/O de test actives · structure figée pour cet essai' : 'Mise à jour du projet en cours'}</div>}
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
        onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
        onNodeClick={(_, node) => { setSelectedId(node.id); setSelectedEdge(null); setInspectorFocus(undefined); }}
        onPaneClick={() => { setSelectedId(null); setSelectedEdge(null); }}
        nodesDraggable={!locked && building} nodesConnectable={!locked && building} deleteKeyCode={locked || !building ? null : ['Backspace', 'Delete']}
        snapToGrid={snapToGrid} snapGrid={[20, 20]} minZoom={.25} maxZoom={2.5}
        fitView fitViewOptions={{ padding: .08 }} proOptions={{ hideAttribution: false }}
        ariaLabelConfig={{ 'controls.zoomIn.ariaLabel': 'Zoom avant', 'controls.zoomOut.ariaLabel': 'Zoom arrière', 'controls.fitView.ariaLabel': 'Centrer le P&ID', 'controls.interactive.ariaLabel': 'Verrouiller le canevas' }}>
        <Background variant={BackgroundVariant.Dots} gap={20} size={.8} color="#c3d1d9" />
        <Controls showInteractive={false} />
        <MiniMap style={{ width: 120, height: 80 }} ariaLabel="Vue d’ensemble du P&ID" pannable zoomable nodeColor={node => node.selected ? '#ef8c52' : '#91b5b8'} maskColor="rgba(242,246,248,.6)" />
      </ReactFlow>
      {!building && inspector}
      {!building && <PlcOutputs project={project} state={state} />}
      {!project.equipment.length && <div className="canvas-empty"><div className="empty-cross"><Plus size={30} /></div><h3>Votre premier procédé</h3><p>Ajoutez une cuve, une pompe ou un instrument<br />depuis la bibliothèque à gauche.</p></div>}
      <div className="pid-legend"><span><i className="legend-pipe" />Conduite</span><span><i className="legend-signal" />Signal</span><span><i className="legend-active" />Actif</span></div>
      <div className="canvas-caption"><span>{visibleEquipment.length} équipements visibles · {edges.length} liaisons</span><span>Modèle de procédé simplifié</span></div>
    </div>

    {flowOpen && <FlowExplanation project={project} state={state} catalog={catalog} equipmentId={selectedId ?? undefined} modelDirty={modelDirty} unavailable={unavailable} onClose={() => setFlowOpen(false)} onFocus={id => { setFlowOpen(false); setSelectedId(id); setSelectedEdge(null); void fitView({ nodes: [{ id }], padding: .8, maxZoom: 1, duration: 200 }); }} />}
    {building && inspector}
    {!building && <AnalogInputs {...controls} />}
    {circuitMode && <TransferBuilder project={project} catalog={catalog} locked={locked} mode={circuitMode} equipmentId={selectedId ?? undefined} onClose={() => setCircuitMode(null)} onApply={(base, next, ids) => { onChange(current => current === base ? next : current); setSelectedId(ids[0] ?? null); setSelectedEdge(null); setInspectorFocus(undefined); setFitAdded(true); }} />}
    {savedCircuitsOpen && <CircuitLibrary project={project} catalog={catalog} locked={locked} mode="browse" onClose={() => setSavedCircuitsOpen(false)} onApply={(base, next, ids) => { onChange(current => current === base ? next : current); setSelectedId(ids[0] ?? null); setSelectedEdge(null); setFitAdded(true); }} />}
  </div>;
}

function ConnectionInspector({ project, id, locked, onChange, onClose }: { project: Project; id: string; locked: boolean; onChange: Props['onChange']; onClose: () => void }) {
  const connection = project.connections.find(connection => connection.id === id);
  if (!connection) return null;
  const change = (patch: Partial<typeof connection>) => onChange(project => ({ ...project, connections: project.connections.map(connection => connection.id === id ? { ...connection, ...patch } : connection) }));
  return <><div className="panel-title">Liaison <button className="icon-button" onClick={onClose} aria-label="Fermer les propriétés"><X size={16} /></button></div>
    <div className="inspector-body"><p className="small-muted">{project.equipment.find(e => e.id === connection.source)?.name} → {project.equipment.find(e => e.id === connection.target)?.name}</p>
      <label>Libellé<input disabled={locked} value={connection.label} onChange={event => change({ label: event.target.value })} /></label>
      <label className="check-label"><input type="checkbox" disabled={locked} checked={connection.directed} onChange={event => change({ directed: event.target.checked })} />Afficher la direction</label>
      <p className="small-muted">Cette ligne décrit le P&ID. Elle ne modifie pas les groupes de débit du modèle.</p>
      <button className="danger-text" disabled={locked} onClick={() => { onChange(project => ({ ...project, connections: project.connections.filter(connection => connection.id !== id) })); onClose(); }}><Unlink size={15} />Supprimer la liaison</button>
    </div></>;
}

function Inspector({ equipment, project, state, catalog, locked, online, unavailable, onChange, onError, onSnapshot, onClose, onCopied, focusRequest, showForces = true }: Props & { equipment: Equipment; onClose: () => void; onCopied: (ids: string[]) => void; showForces?: boolean }) {
  const item = catalog.find(item => item.type === equipment.type);
  const [faultKind, setFaultKind] = useState(FAULTS[equipment.type]?.[0]?.key ?? '');
  const [faultValue, setFaultValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [bindingOpen, setBindingOpen] = useState(false);
  const [connectionTarget, setConnectionTarget] = useState('');
  const [copyOpen, setCopyOpen] = useState(false);
  const [saveCircuitOpen, setSaveCircuitOpen] = useState(false);
  const inspectorBody = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!focusRequest) return;
    if (focusRequest.port) { setBindingOpen(true); return; }
    const field = focusRequest.field?.replace(/^params\./, '');
    if (!field) return;
    const element = Array.from(inspectorBody.current?.querySelectorAll<HTMLElement>('[data-model-field]') ?? []).find(element => element.dataset.modelField === field);
    if (!element) return;
    element.classList.add('focus-target'); element.scrollIntoView({ block: 'nearest' }); element.querySelector<HTMLElement>('input, select')?.focus();
    const timer = setTimeout(() => element.classList.remove('focus-target'), 2400);
    return () => { clearTimeout(timer); element.classList.remove('focus-target'); };
  }, [focusRequest?.nonce]);
  const change = (patch: Partial<Equipment>) => onChange(project => ({ ...project, equipment: project.equipment.map(entry => entry.id === equipment.id ? { ...entry, ...patch } : entry) }));
  const faults = state?.faults[equipment.id] ?? {};
  const waitingForCycle = state?.guided_steps?.at(-1)?.state === 'queued';
  const createTags = () => {
    if (!item) return;
    const { bindings, tags } = missingPortTags(equipment, item);
    if (project.tags.length + tags.length > 200) { onError('Ces variables dépasseraient la limite de 200 tags par projet.'); return; }
    onChange(project => ({ ...project, tags: [...project.tags, ...tags], equipment: project.equipment.map(entry => entry.id === equipment.id ? { ...entry, bindings } : entry) }));
  };
  const mutate = async (path: string, method: string, body?: unknown) => {
    if (waitingForCycle) return;
    setBusy(true);
    try { onSnapshot(await api<Snapshot>(path, method, body)); } catch (error) { onError(String(error instanceof Error ? error.message : error)); } finally { setBusy(false); }
  };
  return <>
    <div className="panel-title"><span>{equipment.name}</span><button className="icon-button" onClick={onClose} aria-label="Fermer les propriétés"><X size={16} /></button></div>
    <div className="inspector-body" ref={inspectorBody}>
      <span className="type-label">{item?.label ?? TYPE_LABELS[equipment.type]}</span>
      <label>Nom / repère<input disabled={locked} value={equipment.name} onChange={event => change({ name: event.target.value })} /></label>
      {item && <div className="binding-launch"><strong>{Object.entries(item.ports).filter(([port, spec]) => project.tags.some(tag => tag.id === equipment.bindings[port] && compatibleTag(tag, spec))).length} / {Object.keys(item.ports).length} rôles associés</strong><p>Choisissez les tags existants ou préparez les tags de cet équipement.</p><button className="button primary full-width" disabled={locked} onClick={() => setBindingOpen(true)}><Link2 size={15} />Lier les tags automate</button></div>}
      {!locked && <div className="quick-connection"><label>Relier à<select aria-label="Relier à" value={connectionTarget} onChange={event => setConnectionTarget(event.target.value)}><option value="">Choisir un équipement</option>{project.equipment.filter(entry => entry.id !== equipment.id && !project.connections.some(edge => edge.source === equipment.id && edge.target === entry.id)).map(entry => <option key={entry.id} value={entry.id}>{entry.name}</option>)}</select></label><button className="button compact-button" disabled={!connectionTarget || project.connections.length >= 200} onClick={() => {
        if (!project.equipment.some(entry => entry.id === connectionTarget) || project.connections.some(edge => edge.source === equipment.id && edge.target === connectionTarget)) return;
        onChange(current => ({ ...current, connections: [...current.connections, { id: uid('line'), source: equipment.id, target: connectionTarget, label: '', directed: true }] })); setConnectionTarget('');
      }}><Link2 size={14} />Tracer la liaison</button><p className="small-muted">Conduite graphique. La cuve et le circuit du modèle se règlent ci-dessous.</p></div>}
      <label>Description<input disabled={locked} value={equipment.description ?? ''} placeholder="Fonction dans le procédé" onChange={event => change({ description: event.target.value })} /></label>
      <label>Unité d’affichage<input disabled={locked} value={equipment.unit ?? ''} placeholder="%, L, bar…" onChange={event => change({ unit: event.target.value })} /></label>

      <AnimationEditor equipment={equipment} project={project} state={state} locked={locked} onChange={animation => change({ animation })} />

      <h4>Paramètres du modèle</h4>
      {Object.entries({ ...item?.default_params, ...(item?.parameters.source_tank_id ? { source_tank_id: '' } : {}), ...equipment.params }).map(([key, value]) => {
        const spec = item?.parameters[key];
        const label = (spec?.label ?? key).replace(' (identifiant)', '');
        const isEquipment = key === 'tank_id' || key === 'source_equipment' || key === 'source_tank_id';
        const options = spec?.options;
        return <label key={key} data-model-field={key} className={typeof value === 'boolean' ? 'check-label' : ''}>
          {typeof value !== 'boolean' && <span>{label}{spec?.unit && <small>{spec.unit}</small>}</span>}
          {typeof value === 'boolean' ? <><input type="checkbox" disabled={locked} checked={value} onChange={event => change({ params: { ...equipment.params, [key]: event.target.checked } })} />{label}</>
            : isEquipment ? <select disabled={locked} value={String(value)} onChange={event => change({ params: { ...equipment.params, [key]: event.target.value } })}><option value="">{key === 'source_tank_id' ? 'Source extérieure' : '— Choisir —'}</option>{project.equipment.filter(entry => entry.id !== equipment.id && (key === 'source_equipment' || entry.type === 'tank')).map(entry => <option key={entry.id} value={entry.id}>{entry.name}</option>)}</select>
              : options ? <select disabled={locked} value={String(value)} onChange={event => change({ params: { ...equipment.params, [key]: event.target.value } })}>{options.map(option => <option key={typeof option === 'string' ? option : option.value} value={typeof option === 'string' ? option : option.value}>{typeof option === 'string' ? option : option.label}</option>)}</select>
                : <input disabled={locked} type={typeof value === 'number' ? 'number' : 'text'} step="any" min={spec?.min} max={spec?.max} value={String(value)} onChange={event => change({ params: { ...equipment.params, [key]: typeof value === 'number' ? Number(event.target.value) : event.target.value } })} />}
        </label>;
      })}

      <h4>Variables associées</h4>
      <p className="small-muted">Entrée = capteur vers PLC.<br />Sortie = commande du PLC.</p>
      {Object.entries(item?.ports ?? {}).map(([port, spec]) => {
        const tagId = equipment.bindings[port] ?? '';
        const tag = project.tags.find(tag => tag.id === tagId);
        const incompatible = Boolean(tagId && (!tag || tag.direction !== spec.direction || !spec.data_types.includes(tag.data_type)));
        return <div className="binding-field" key={port}>
          <label><span>{spec.label ?? port}{spec.required && <em> *</em>}<small>{spec.direction === 'input' ? '→ PLC' : '← PLC'}</small></span>
            <select disabled={locked} aria-invalid={incompatible || (spec.required && !tagId)} className={incompatible || (spec.required && !tagId) ? 'missing' : ''} value={tagId} onChange={event => { const bindings = { ...equipment.bindings }; if (event.target.value) bindings[port] = event.target.value; else delete bindings[port]; change({ bindings }); }}>
              <option value="">— Non associé —</option>{incompatible && <option value={tagId} disabled>{tag?.name ?? tagId} · incompatible</option>}{project.tags.filter(tag => tag.direction === spec.direction && spec.data_types.includes(tag.data_type)).map(tag => <option key={tag.id} value={tag.id}>{tag.name}</option>)}
            </select>
          </label>
          {incompatible && <p className="inline-error">Association incompatible : choisissez une variable {spec.data_types.join(' / ')} de sens {spec.direction === 'input' ? 'entrée PLC' : 'sortie PLC'}.</p>}
          {tag && <div className="binding-value"><span>{tag.data_type}</span><strong>{fmt(state?.tags[tag.id]?.value ?? tag.initial_value)} {tag.unit}</strong></div>}
          {showForces && tag?.direction === 'input' && state?.run_id && <ForceField key={tag.id} tag={tag} state={state} unavailable={unavailable ?? (incompatible ? 'Associez une variable compatible avant de forcer la mesure.' : undefined)} onError={onError} onSnapshot={onSnapshot} />}
        </div>;
      })}
      {!locked && <button className="button compact-button full-width" onClick={createTags} disabled={project.tags.length >= 200}><WandSparkles size={14} />Créer les tags manquants</button>}

      {(FAULTS[equipment.type]?.length ?? 0) > 0 && <>
        <h4>Injection de défaut</h4>
        {waitingForCycle && <p className="small-muted">STEP en attente du cycle d’échange. Commandes I/O temporairement suspendues.</p>}
        <select aria-label="Type de défaut" value={faultKind} onChange={event => { setFaultKind(event.target.value); setFaultValue(''); }}>{FAULTS[equipment.type]?.map(fault => <option key={fault.key} value={fault.key}>{fault.label}</option>)}</select>
        {['out_of_range', 'valve_stuck'].includes(faultKind) && <label>Valeur {faultKind === 'valve_stuck' ? 'de position (%)' : 'hors plage'}<input type="number" step="any" value={faultValue} placeholder={faultKind === 'valve_stuck' ? '0' : '120'} onChange={event => setFaultValue(event.target.value)} /></label>}
        <div className="button-row"><button className="button warning-button compact-button" disabled={!online || !state?.run_id || !['running', 'paused'].includes(state.status) || state.scenario.state === 'completed' || busy || waitingForCycle} onClick={() => void mutate('/fault', 'POST', { equipment_id: equipment.id, kind: faultKind, ...(faultValue !== '' ? { value: Number(faultValue) } : {}) })}><Zap size={14} />Injecter</button>
          <button className="button compact-button" disabled={!online || !Object.keys(faults).length || busy || waitingForCycle} onClick={() => void mutate(`/fault/${encodeURIComponent(equipment.id)}`, 'DELETE')}><RotateCcw size={14} />Lever</button></div>
        {Object.keys(faults).length > 0 && <div className="active-faults">{Object.keys(faults).map(key => <span key={key}>{FAULTS[equipment.type]?.find(fault => fault.key === key)?.label ?? key}</span>)}</div>}
        {!state?.run_id && <p className="small-muted">Démarrez un essai pour injecter un défaut.</p>}
      </>}
      <div className="circuit-duplicate"><button className="button compact-button" disabled={locked} onClick={() => setCopyOpen(true)}><Copy size={14} />Dupliquer cet équipement ou son circuit</button>{isFlowEquipment(equipment) && <button className="button compact-button" disabled={locked} onClick={() => setSaveCircuitOpen(true)}>Enregistrer ce circuit</button>}</div>
      <div className="inspector-footer"><span className="mono">{equipment.id}</span><button className="danger-text" disabled={locked} onClick={() => { if (window.confirm(`Supprimer ${equipment.name} et ses liaisons graphiques ? Ses tags seront conservés.`)) { onChange(project => ({ ...project, equipment: project.equipment.filter(entry => entry.id !== equipment.id), connections: project.connections.filter(connection => connection.source !== equipment.id && connection.target !== equipment.id) })); onClose(); } }}><Trash2 size={14} />Supprimer</button></div>
    </div>
    {bindingOpen && item && <BindingEditor project={project} equipment={equipment} item={item} catalog={catalog} locked={locked} initialPort={focusRequest?.port} onChange={onChange} onClose={() => setBindingOpen(false)} />}
    {copyOpen && <TransferBuilder project={project} catalog={catalog} locked={locked} mode="duplicate" equipmentId={equipment.id} onClose={() => setCopyOpen(false)} onApply={(base, next, ids) => { onChange(current => current === base ? next : current); onCopied(ids); }} />}
    {saveCircuitOpen && <CircuitLibrary project={project} catalog={catalog} locked={locked} mode="save" equipmentId={equipment.id} onClose={() => setSaveCircuitOpen(false)} onApply={(base, next, ids) => { onChange(current => current === base ? next : current); onCopied(ids); }} />}
  </>;
}

export default function PidCanvas(props: Props) { return <ReactFlowProvider><Canvas {...props} /></ReactFlowProvider>; }
