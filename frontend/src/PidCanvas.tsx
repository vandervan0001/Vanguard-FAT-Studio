import { memo, useCallback, useEffect, useId, useMemo, useRef, useState, type CSSProperties } from 'react';
import {
  ReactFlow, ReactFlowProvider, Background, BackgroundVariant, Controls, MiniMap,
  Handle, Position, MarkerType, ConnectionMode, useReactFlow, useUpdateNodeInternals, BaseEdge, getSmoothStepPath,
  type Node, type NodeProps, type NodeChange, type EdgeChange, type Connection, type EdgeProps,
} from '@xyflow/react';
import { CircleHelp, GripVertical, Plus, Trash2, Unlink, WandSparkles, X, Zap, RotateCcw, PencilRuler, Radio } from 'lucide-react';
import { api } from './api';
import { fmt, uid, type CatalogItem, type Equipment, type EquipmentType, type PidRotation, type PidSymbolDefinition, type Project, type Snapshot, type Tag, type Scenario } from './types';
import { DigitalInputs, AnalogInputs, PlcOutputs } from './TestConsole';
import { ForceField } from './ForceField';
import { scenarioFocus } from './ScenarioRun';
import { AnimationEditor, animationReading } from './AnimationEditor';
import { diagnosticLabel, diagnosticProfile, displayValue, engineeringUnit } from './signal';
import PidSymbolSvg, { rotatedPort, symbolDefinition } from './PidSymbolSvg';
import { serviceCode, serviceDefinition, usePidConventions } from './pidConventions';
import './pid-symbols.css';

type Props = {
  project: Project; state: Snapshot | null; catalog: CatalogItem[]; locked: boolean; online: boolean;
  onChange: (update: (project: Project) => Project) => void;
  onError: (message: string) => void; onSnapshot: (state: Snapshot) => void;
  scenario?: Scenario | null; viewRequest?: number; presentation?: boolean; unavailable?: string;
};
type EquipmentNode = Node<{ equipment: Equipment; definition?: PidSymbolDefinition; state: Record<string, unknown>; tags: Snapshot['tags']; faults: Record<string, unknown>; locked: boolean; operating: boolean; highlighted?: boolean; signalTag?: Tag; animationDataType?: Tag['data_type'] }, 'equipment'>;

const TYPE_LABELS: Record<EquipmentType, string> = { tank: 'Cuve', pump: 'Pompe', pump_vfd: 'Pompe à variateur', valve_onoff: 'Vanne TOR', valve_control: 'Vanne modulante', analog_sensor: 'Capteur analogique', digital_sensor: 'Capteur binaire', digital_input: 'Bouton / entrée TOR', indicator: 'Indicateur', pid_symbol: 'Symbole P&ID', heat_exchanger: 'Échangeur simulé', valve_three_way: 'Vanne trois voies simulée' };
const PREFIX: Record<EquipmentType, string> = { tank: 'TK', pump: 'P', pump_vfd: 'VFD', valve_onoff: 'XV', valve_control: 'CV', analog_sensor: 'AI', digital_sensor: 'DI', digital_input: 'PB', indicator: 'ST', pid_symbol: 'EQ', heat_exchanger: 'E', valve_three_way: 'V' };
const librarySearch = (value: string) => value.normalize('NFD').replace(/\p{M}/gu, '').toLocaleLowerCase('fr').replace(/\b3(?=\s*voies)/g, 'trois').replace(/\b4(?=\s*voies)/g, 'quatre');
const PORT_LABELS: Record<string, string> = { primary_in: 'P1', primary_out: 'P2', secondary_in: 'S1', secondary_out: 'S2' };
const portLabel = (id: string) => PORT_LABELS[id] ?? id;
const physicalMultiport = (type: EquipmentType) => type === 'heat_exchanger' || type === 'valve_three_way';
const drawingDefinition = (symbols: PidSymbolDefinition[], equipment: Pick<Equipment, 'type' | 'symbol_kind'>) => equipment.type === 'pid_symbol' ? symbolDefinition(symbols, equipment.symbol_kind) : physicalMultiport(equipment.type) ? symbolDefinition(symbols, equipment.type === 'valve_three_way' ? 'three_way_valve' : 'heat_exchanger') : undefined;
const FLOW_SOURCES: EquipmentType[] = ['pump', 'pump_vfd', 'valve_onoff', 'valve_control', 'valve_three_way'];
const FAULTS: Partial<Record<EquipmentType, { key: string; label: string }[]>> = {
  pump: [{ key: 'motor_trip', label: 'Défaut moteur' }],
  pump_vfd: [{ key: 'motor_trip', label: 'Défaut moteur' }],
  valve_onoff: [{ key: 'valve_stuck', label: 'Vanne bloquée' }],
  valve_control: [{ key: 'valve_stuck', label: 'Vanne bloquée' }],
  valve_three_way: [{ key: 'valve_stuck', label: 'Vanne bloquée' }],
  heat_exchanger: [{ key: 'fouling', label: 'Encrassement thermique' }],
  analog_sensor: [{ key: 'sensor_stuck', label: 'Capteur figé' }, { key: 'out_of_range', label: 'Signal hors plage' }],
  digital_sensor: [{ key: 'sensor_stuck', label: 'Capteur figé' }],
};

function PhysicalReadings({ equipment, state, unavailable }: { equipment: Equipment; state: Record<string, unknown>; unavailable: boolean }) {
  const fields = equipment.type === 'heat_exchanger'
    ? [['primary_outlet_temperature_c', 'Sortie P', '°C'], ['secondary_outlet_temperature_c', 'Sortie S', '°C'], ['heat_kw', 'P → S', 'kW']]
    : [['position', 'Position vers A', '%'], ['flow_a_l_s', 'Branche A', 'L/s'], ['flow_b_l_s', 'Branche B', 'L/s']];
  return <dl className="pid-physical-readings" aria-label={`Mesures simulées de ${equipment.name}`}>
    {fields.map(([field, label, unit]) => {
      const value = state[field];
      return <div key={field} data-field={field}><dt>{label}</dt><dd>{unavailable ? 'Indisponible' : typeof value === 'number' && Number.isFinite(value) ? `${field === 'heat_kw' && value >= 0 ? '+' : ''}${fmt(value, 2)} ${unit}` : '—'}</dd></div>;
    })}
  </dl>;
}

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
  const documentary = equipment.type === 'pid_symbol';
  const modelled = physicalMultiport(equipment.type);
  const multiport = documentary || modelled;
  const updateNodeInternals = useUpdateNodeInternals();
  useEffect(() => { updateNodeInternals(equipment.id); }, [equipment.id, equipment.rotation, equipment.symbol_kind, data.definition, updateNodeInternals]);
  const ports = data.definition?.ports.map(port => rotatedPort(port, equipment.rotation)) ?? [];
  const primaryPort = equipment.type === 'tank' ? 'level' : equipment.type === 'pump_vfd' ? 'speed' : equipment.type === 'pump' ? 'feedback' : equipment.type.startsWith('valve') ? 'position' : 'value';
  const portValue = tags[equipment.bindings[primaryPort]]?.value;
  const value = equipment.type === 'tank' ? state.level_percent ?? state.level ?? portValue : portValue ?? state[equipment.type === 'pump' ? 'running' : primaryPort] ?? state.value;
  const physicalValue = equipment.type.startsWith('valve') ? state.position ?? value : state.running ?? value;
  const visual = equipment.animation ? animationReading(equipment.animation, tags[equipment.animation.tag_id], data.animationDataType) : null;
  const badBinding = Object.values(equipment.bindings).some(id => /bad|stale|error|disconnected/i.test(tags[id]?.quality ?? ''));
  const unavailable = badBinding || Boolean(visual && !visual.available && !visual.initial);
  const active = !unavailable && (visual ? visual.active : modelled ? Math.abs(Number(state[equipment.type === 'heat_exchanger' ? 'heat_kw' : 'flow_l_s'] ?? 0)) > .001 : typeof physicalValue === 'boolean' ? physicalValue : typeof physicalValue === 'number' && physicalValue > 0);
  const faulted = Object.keys(faults).length > 0 || Boolean(state.fault);
  const forced = Object.values(equipment.bindings).some(id => tags[id]?.forced);
  const scaledTag = equipment.type === 'analog_sensor' && data.signalTag?.signal ? data.signalTag : null;
  const profile = scaledTag ? diagnosticProfile(scaledTag, tags[scaledTag.id]) : null;
  const reading = unavailable || value === undefined ? undefined : profile ? diagnosticLabel(profile) : visual?.available && ['level', 'position'].includes(equipment.animation?.effect ?? '') ? visual.percent : scaledTag ? displayValue(scaledTag, value as number, 'engineering') : value;
  const unit = scaledTag ? engineeringUnit(scaledTag) : primaryPort === 'level' || primaryPort === 'position' || primaryPort === 'speed' ? '%' : equipment.unit;
  const level = unavailable ? 0 : visual?.available && ['level', 'position'].includes(equipment.animation?.effect ?? '') ? visual.percent : Number(state.level_percent ?? state.level ?? state.position ?? value ?? equipment.params.initial_level_pct ?? 0);
  const style = { '--symbol-active': equipment.animation?.active_color ?? '#078f79', '--symbol-inactive': unavailable ? '#b47b60' : equipment.animation?.inactive_color ?? '#607a8d' } as CSSProperties;
  const animationClass = !unavailable && visual?.available && visual.active ? `animation-${equipment.animation?.effect}` : '';
  return <div className={`equipment-node type-${equipment.type} ${multiport ? 'pid-multiport-node' : ''} ${equipment.type === 'tank' ? 'tank-node' : ''} ${selected ? 'selected' : ''} ${faulted ? 'faulted' : ''} ${unavailable ? 'quality-unavailable' : ''} ${forced ? 'forced-node' : ''} ${data.highlighted ? 'fat-focus' : ''} ${animationClass}`} style={style} data-animation-active={visual ? String(!unavailable && visual.available && visual.active) : undefined} data-animation-quality={visual ? unavailable ? 'unavailable' : visual.available ? 'available' : 'initial' : undefined} title={equipment.description || equipment.name}>
    <Handle type="target" position={Position.Left} className={multiport ? 'pid-legacy-handle' : undefined} isConnectable={!data.locked && !multiport} />
    {data.operating && [Position.Left, Position.Right, Position.Top, Position.Bottom].flatMap(position => ['source', 'target'].map(type => <Handle key={`${type}-${position}`} id={`${type}-${position}`} className="routing-handle" type={type as 'source' | 'target'} position={position} isConnectable={false} />))}
    <div className="node-label"><span>{equipment.name.split(' · ')[0]}</span>{unavailable ? <span className="node-alert">QUALITÉ</span> : faulted ? <span className="node-alert">DÉFAUT</span> : forced ? <span className="node-force">FORCÉ</span> : null}</div>
    <div className="node-description">{equipment.name.includes(' · ') ? equipment.name.split(' · ').slice(1).join(' · ') : documentary ? data.definition?.label ?? 'Symbole non identifié' : TYPE_LABELS[equipment.type]}</div>
    {modelled && <span className="pid-model-badge">Modèle simulé</span>}
    {multiport ? <div className="pid-symbol-body" data-rotation={equipment.rotation ?? 0}>
      <PidSymbolSvg definition={data.definition} rotation={equipment.rotation} />
      {ports.map(port => {
        const position = port.x <= 10 ? Position.Left : port.x >= 90 ? Position.Right : port.y <= 50 ? Position.Top : Position.Bottom;
        const style = { left: `${port.x}%`, top: `${port.y}%`, right: 'auto', bottom: 'auto', transform: 'translate(-50%, -50%)' };
        return <span key={port.id}>
          <Handle id={port.id} type="target" position={position} className="pid-symbol-target" style={style} isConnectable={false} />
          <Handle id={port.id} type="source" position={position} className="pid-symbol-handle" style={style} isConnectable={!data.locked} data-port-id={port.id} aria-label={`Piquage ${port.id} de ${equipment.name}`} title={`${port.id} · ${port.label}`} />
          <span className={`pid-port-label port-${position}`} style={{ left: `${port.x}%`, top: `${port.y}%` }} title={`${port.id} · ${port.label}`}>{portLabel(port.id)}</span>
        </span>;
      })}
    </div> : <ProcessSymbol type={equipment.type} active={active} level={level} label={equipment.name.split(' · ')[0]} />}
    {modelled ? <PhysicalReadings equipment={equipment} state={state} unavailable={unavailable} /> : <div className={`node-value ${!documentary && active ? 'is-active' : ''}`}>{documentary ? 'Non simulé' : unavailable ? 'Indisponible' : reading === undefined ? TYPE_LABELS[equipment.type] : `${fmt(reading)}${typeof reading === 'number' && unit ? ' ' + unit : ''}`}</div>}
    <Handle type="source" position={Position.Right} className={multiport ? 'pid-legacy-handle' : undefined} isConnectable={!data.locked && !multiport} />
  </div>;
});
const nodeTypes = { equipment: SymbolNode };

function ProcessPipe(props: EdgeProps) {
  const [path, labelX, labelY] = getSmoothStepPath({ sourceX: props.sourceX, sourceY: props.sourceY, targetX: props.targetX, targetY: props.targetY, sourcePosition: props.sourcePosition, targetPosition: props.targetPosition, borderRadius: 14, offset: 28 });
  const instrument = props.data?.instrument;
  return <><BaseEdge id={props.id} path={path} markerEnd={props.markerEnd} label={props.label} labelX={labelX} labelY={labelY} labelStyle={props.labelStyle} labelBgStyle={props.labelBgStyle} style={{ ...props.style, strokeWidth: instrument ? 1.5 : props.selected ? 6 : 5, strokeDasharray: instrument ? '5 5' : undefined }} /><path d={path} data-edge-id={props.id} data-flowing={String(Boolean(props.data?.flowing))} data-service={String(props.data?.service ?? 'unspecified')} className={`pipe-core ${props.data?.flowing ? 'flowing' : ''}`} fill="none" stroke={instrument || props.data?.assignedService ? 'none' : '#d3e4e7'} strokeWidth="2" pointerEvents="none" /></>;
}
const edgeTypes = { process: ProcessPipe };

function Canvas({ project, state, catalog, locked, online, unavailable, onChange, onError, onSnapshot, scenario, viewRequest, presentation }: Props) {
  const { conventions, error: conventionsError } = usePidConventions();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [libraryQuery, setLibraryQuery] = useState('');
  const [snapToGrid, setSnapToGrid] = useState(true);
  const [building, setBuilding] = useState(!project.equipment.length);
  const [showConsoles, setShowConsoles] = useState(false);
  const [measurements, setMeasurements] = useState<Record<string, { width: number; height: number }>>({});
  const canvasRef = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition, fitView } = useReactFlow();
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
  const symbols = useMemo(() => catalog.find(item => item.type === 'pid_symbol')?.symbols ?? [], [catalog]);
  const models = catalog.filter(item => item.type !== 'pid_symbol');
  const searchedModels = models.filter(item => librarySearch(`${item.label} ${item.description}`).includes(librarySearch(libraryQuery)));
  const searchedSymbols = symbols.filter(symbol => librarySearch(`${symbol.label} ${symbol.id} ${symbol.category}`).includes(librarySearch(libraryQuery)));
  const symbolCategories = [...new Set(searchedSymbols.map(symbol => symbol.category))];
  const visibleEquipment = useMemo(() => project.equipment.filter(item => building || !['digital_input', 'indicator'].includes(item.type)), [project.equipment, building]);
  const nodes = useMemo<EquipmentNode[]>(() => visibleEquipment.map(equipment => ({
    id: equipment.id, type: 'equipment', position: equipment.position, measured: measurements[equipment.id], selected: selectedId === equipment.id,
    data: { equipment, definition: drawingDefinition(symbols, equipment), state: state?.equipment[equipment.id] ?? {}, tags: state?.tags ?? {}, faults: state?.faults[equipment.id] ?? {}, locked: locked || !building, operating: !building, highlighted: focusedIds.includes(equipment.id), signalTag: project.tags.find(tag => tag.id === equipment.bindings.value), animationDataType: project.tags.find(tag => tag.id === equipment.animation?.tag_id)?.data_type },
  })), [visibleEquipment, symbols, state?.equipment, state?.tags, state?.faults, selectedId, locked, building, focusedIds, measurements, project.tags]);
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
    const flowField = (equipment: Equipment, port: string | undefined) => equipment.type === 'heat_exchanger' ? port?.startsWith('primary_') ? 'primary_flow_l_s' : port?.startsWith('secondary_') ? 'secondary_flow_l_s' : '' : equipment.type === 'valve_three_way' ? port === 'A' ? 'flow_a_l_s' : port === 'B' ? 'flow_b_l_s' : port === 'AB' ? 'flow_l_s' : '' : 'flow_l_s';
    const fields = [flowField(source, connection.source_port), flowField(target, connection.target_port)];
    const flows = [source, target].map((item, index) => state?.equipment[item.id]?.[fields[index]]).filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
    const documentary = source.type === 'pid_symbol' || target.type === 'pid_symbol';
    const flowing = !documentary && !instrument && !unavailable && fields.every(Boolean) && state?.status === 'running' && flows.length > 0 && Math.min(...flows) > .001;
    const handle = (equipment: Equipment, port: string | undefined, type: 'source' | 'target', side: string) => drawingDefinition(symbols, equipment)?.ports.some(item => item.id === port) ? port : !building ? `${type}-${side}` : undefined;
    const service = serviceDefinition(conventions, connection.service);
    const assignedService = Boolean(connection.service && connection.service !== 'unspecified');
    const code = serviceCode(conventions, connection.service);
    const monochrome = project.pid_drawing?.color_mode === 'monochrome';
    const stroke = monochrome ? '#000000' : assignedService ? service?.color ?? '#000000' : selectedEdge === connection.id ? '#dd8a4c' : unavailable ? '#bf9878' : instrument ? '#9baeb8' : flowing ? '#1a9b87' : '#668d99';
    return { ...connection, className: assignedService || monochrome ? 'pid-service-edge' : undefined, label: [code && `[${code}]`, connection.label].filter(Boolean).join(' · '), type: 'process', selected: selectedEdge === connection.id,
      sourceHandle: handle(source, connection.source_port, 'source', from), targetHandle: handle(target, connection.target_port, 'target', to), data: { instrument, flowing, service: connection.service ?? 'unspecified', assignedService },
      style: { stroke, '--pid-service-color': stroke } as CSSProperties,
      ...(connection.directed && !instrument ? { markerEnd: { type: MarkerType.ArrowClosed, color: stroke, width: 14, height: 14 } } : {}),
      labelStyle: { fill: '#527080', fontSize: 11 }, labelBgStyle: { fill: '#f5f9fa', fillOpacity: .96 },
    };
  }), [project.connections, project.pid_drawing?.color_mode, conventions, visibleEquipment, symbols, selectedEdge, state?.status, state?.equipment, state?.tags, state?.connection.quality, building]);
  const usedServices = conventions?.services.filter(service => service.id !== 'unspecified' && project.connections.some(connection => connection.service === service.id)) ?? [];

  const addEquipment = (type: EquipmentType, position?: { x: number; y: number }, definition?: PidSymbolDefinition) => {
    if (locked || !building) return;
    if (project.equipment.length >= 50) { onError('Le projet est limité à 50 équipements.'); return; }
    const item = catalog.find(item => item.type === type);
    if (!item) return;
    const id = uid(type);
    const count = project.equipment.filter(equipment => equipment.type === type && (type !== 'pid_symbol' || equipment.symbol_kind === definition?.id)).length + 101;
    const prefix = definition?.prefix ?? PREFIX[type];
    let number = count;
    while (project.equipment.some(equipment => equipment.name === `${prefix}-${number}`)) number++;
    onChange(project => ({ ...project, equipment: [...project.equipment, {
      id, type, name: `${prefix}-${number}`, description: definition?.description ?? '', unit: '',
      ...(type === 'pid_symbol' ? { symbol_kind: definition?.id ?? 'generic', source_kind: '', rotation: 0 as const } : {}),
      position: position ?? screenToFlowPosition({ x: window.innerWidth / 2, y: window.innerHeight / 2 }),
      params: { ...item.default_params }, bindings: {},
    }] }));
    setSelectedId(id);
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
    const source_port = connection.sourceHandle?.startsWith('source-') ? '' : connection.sourceHandle ?? '';
    const target_port = connection.targetHandle?.startsWith('target-') ? '' : connection.targetHandle ?? '';
    if (project.connections.some(edge => edge.source === connection.source && edge.target === connection.target && (edge.source_port ?? '') === source_port && (edge.target_port ?? '') === target_port)) return;
    if (project.connections.length >= 200) { onError('Le projet est limité à 200 liaisons.'); return; }
    onChange(project => ({ ...project, connections: [...project.connections, { id: uid('line'), source: connection.source, target: connection.target, source_port, target_port, label: '', directed: true }] }));
  };

  const controls = { project, state, unavailable, onError, onSnapshot };
  const inspector = selected || selectedEdge || building ? <aside className="inspector panel">
    {selected ? <Inspector key={selected.id} equipment={selected} project={project} state={state} catalog={catalog} locked={locked || !building} online={online} unavailable={unavailable} onChange={onChange} onError={onError} onSnapshot={onSnapshot} showForces={building} onClose={() => setSelectedId(null)} />
      : selectedEdge ? <ConnectionInspector project={project} catalog={catalog} id={selectedEdge} locked={locked || !building} onChange={onChange} onClose={() => setSelectedEdge(null)} />
        : <><div className="panel-title">Propriétés</div><div className="inspector-empty"><ProcessSymbol type="tank" /><h3>Sélectionnez un équipement</h3><p>Ses paramètres, ses variables PLC et ses défauts de simulation apparaîtront ici.</p></div><div className="model-note"><strong>Débits et liaisons</strong><p>Les conduites sont graphiques. Le débit est défini par la cuve cible, le sens et le groupe de débit de chaque pompe ou vanne.</p><p>Dans un même groupe, l’équipement le plus limitant fixe le débit. Les groupes indépendants s’additionnent.</p></div></>}
  </aside> : null;
  return <div className={`workbench ${building ? 'building-mode' : 'operating-mode'} ${presentation && !building ? 'presented-workbench' : ''} ${presentation && !showConsoles && !building ? 'consoles-hidden' : ''}`}>
    {building ? <aside className="palette panel">
      <div className="panel-title">Bibliothèque <span className="subtle-count">{models.length + symbols.length}</span></div>
      <p className="panel-hint">Glissez un équipement<br />sur le P&ID.</p>
      <div className="palette-items">
        <label className="pid-library-search">Rechercher dans la bibliothèque<input type="search" value={libraryQuery} onChange={event => setLibraryQuery(event.target.value)} placeholder="Échangeur, 3 voies…" /></label>
        {searchedModels.length > 0 && <h3 className="pid-library-group">Modèles simulés <span>{models.length}</span></h3>}
        {searchedModels.map(item => <button key={item.type} className="palette-item" draggable={!locked && project.equipment.length < 50} disabled={locked || project.equipment.length >= 50}
          onDragStart={event => { event.dataTransfer.setData('application/fat-equipment', item.type); event.dataTransfer.effectAllowed = 'move'; }}
          onClick={() => addEquipment(item.type)} title={`${item.description}\nCliquer ou glisser pour ajouter`}>
          {physicalMultiport(item.type) ? <PidSymbolSvg definition={drawingDefinition(symbols, { type: item.type })} compact /> : <ProcessSymbol type={item.type} compact />}<span>{item.label}</span><GripVertical size={13} className="drag-hint" />
        </button>)}
        {symbols.length > 0 && <section className="pid-document-library" aria-label="Symboles P&ID documentaires">
          <h3 className="pid-library-group">Symboles P&ID <span>{symbols.length}</span></h3>
          <p className="pid-library-notice">Symboles documentaires · non simulés</p>
          {symbolCategories.map(category => <div key={category}><h4 className="pid-library-category">{category}</h4>
            {searchedSymbols.filter(symbol => symbol.category === category).map(symbol => <button key={symbol.id} className="palette-item pid-symbol-palette-item" draggable={!locked && project.equipment.length < 50} disabled={locked || project.equipment.length >= 50}
              onDragStart={event => { event.dataTransfer.setData('application/fat-equipment', `pid:${symbol.id}`); event.dataTransfer.effectAllowed = 'move'; }}
              onClick={() => addEquipment('pid_symbol', undefined, symbol)} aria-label={`Ajouter ${symbol.label}`} title={symbol.description}>
              <PidSymbolSvg definition={symbol} compact /><span>{symbol.label}</span><GripVertical size={13} className="drag-hint" />
            </button>)}
          </div>)}
          {!searchedSymbols.length && <p className="pid-library-notice">Aucun symbole correspondant.</p>}
        </section>}
      </div>
      <div className="palette-note"><CircleHelp size={15} /><p>Reliez les points latéraux pour dessiner une conduite.</p></div>
      <label className="check-label grid-choice"><input type="checkbox" checked={snapToGrid} onChange={event => setSnapToGrid(event.target.checked)} />Aligner sur la grille</label>
      <div className="keyboard-help"><kbd>Suppr</kbd> supprimer<br /><kbd>Molette</kbd> zoomer<br /><kbd>Glisser fond</kbd> déplacer</div>
    </aside> : <DigitalInputs {...controls} />}

    <div ref={canvasRef} className="canvas-area" onDragOver={event => { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; }}
      onDrop={event => { event.preventDefault(); const value = event.dataTransfer.getData('application/fat-equipment'); const position = screenToFlowPosition({ x: event.clientX, y: event.clientY }); const symbol = symbols.find(symbol => `pid:${symbol.id}` === value); if (symbol) addEquipment('pid_symbol', position, symbol); else if (models.some(item => item.type === value)) addEquipment(value as EquipmentType, position); }}>
      <div className="canvas-topline"><span><span className={`small-dot ${state?.status === 'running' ? 'green' : ''}`} />{building ? 'CONSTRUCTION DU PROCÉDÉ' : project.name.toLocaleUpperCase('fr-CH')}</span><div>{presentation && !building && <button aria-pressed={showConsoles} onClick={() => setShowConsoles(value => !value)}>{showConsoles ? 'Masquer les pupitres' : 'Afficher les pupitres'}</button>}<button className="canvas-mode" disabled={locked} onClick={() => { setBuilding(value => !value); setSelectedId(null); setSelectedEdge(null); }}>{building ? <Radio size={12} /> : <PencilRuler size={12} />}{building ? 'Tester les I/O' : 'Construire'}</button><button onClick={() => fitView({ padding: .12, duration: 200 })}>Vue complète</button></div></div>
      {locked && <div className="editing-locked">{!online ? 'Service indisponible · commandes désactivées' : state?.guided_steps?.at(-1)?.state === 'queued' ? 'STEP en attente du cycle d’échange · I/O temporairement suspendues' : state?.status === 'paused' ? 'Essai en pause · structure figée · reprendre pour les impulsions' : state?.status === 'running' ? 'I/O de test actives · structure figée pour cet essai' : 'Mise à jour du projet en cours'}</div>}
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} connectionMode={ConnectionMode.Loose}
        onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
        onNodeClick={(_, node) => { setSelectedId(node.id); setSelectedEdge(null); }}
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
      <div className="pid-legend" aria-label="Légende du P&ID"><span><i className="legend-pipe" />Conduite</span><span><i className="legend-signal" />Signal</span><span><i className="legend-active" />Flux animé</span>{usedServices.map(service => <span key={service.id} className="pid-legend-service"><i aria-hidden="true" style={{ borderColor: project.pid_drawing?.color_mode === 'monochrome' ? '#000000' : service.color }} /><code>{service.code}</code>{service.label}</span>)}{usedServices.length > 0 && <small>Couleurs de service : convention du projet</small>}{conventionsError && <small role="status">Références des services indisponibles. Rechargez la page pour réessayer.</small>}</div>
      <div className="canvas-caption"><span>{visibleEquipment.length} équipements visibles · {edges.length} liaisons</span><span>Modèle de procédé simplifié</span></div>
    </div>

    {building && inspector}
    {!building && <AnalogInputs {...controls} />}
  </div>;
}

function ConnectionInspector({ project, catalog, id, locked, onChange, onClose }: { project: Project; catalog: CatalogItem[]; id: string; locked: boolean; onChange: Props['onChange']; onClose: () => void }) {
  const { conventions, error: conventionsError } = usePidConventions();
  const connection = project.connections.find(connection => connection.id === id);
  if (!connection) return null;
  const change = (patch: Partial<typeof connection>) => onChange(project => ({ ...project, connections: project.connections.map(connection => connection.id === id ? { ...connection, ...patch } : connection) }));
  const symbols = catalog.find(item => item.type === 'pid_symbol')?.symbols ?? [];
  const endpoint = (side: 'source' | 'target') => {
    const equipment = project.equipment.find(item => item.id === connection[side]);
    const ports = equipment ? drawingDefinition(symbols, equipment)?.ports ?? [] : [];
    const key = side === 'source' ? 'source_port' : 'target_port';
    const current = connection[key] ?? '';
    return <label>{side === 'source' ? 'Piquage source' : 'Piquage cible'}<select disabled={locked || !ports.length} value={current} onChange={event => change({ [key]: event.target.value })}>
      <option value="">Raccord automatique</option>{current && !ports.some(port => port.id === current) && <option value={current}>{current} · source conservée</option>}
      {ports.map(port => <option key={port.id} value={port.id}>{port.id} · {port.label}</option>)}
    </select>{current && !ports.some(port => port.id === current) && <span className="pid-port-warning" role="status">Piquage « {current} » conservé sans position connue. Raccord automatique affiché ; vérifiez le document source.</span>}</label>;
  };
  return <><div className="panel-title">Liaison <button className="icon-button" onClick={onClose} aria-label="Fermer les propriétés"><X size={16} /></button></div>
    <div className="inspector-body"><p className="small-muted">{project.equipment.find(e => e.id === connection.source)?.name} → {project.equipment.find(e => e.id === connection.target)?.name}</p>
      <label>Libellé<input disabled={locked} value={connection.label} onChange={event => change({ label: event.target.value })} /></label>
      <label>Service de la liaison<select aria-label="Service de la liaison" disabled={locked || !conventions} value={connection.service ?? 'unspecified'} onChange={event => change({ service: event.target.value as typeof connection.service })}>{!conventions && <option value={connection.service ?? 'unspecified'}>{connection.service && connection.service !== 'unspecified' ? connection.service : 'Non renseigné'}</option>}{conventions?.services.map(service => <option key={service.id} value={service.id}>{service.code ? `${service.code} · ` : ''}{service.label}</option>)}</select></label>
      {conventionsError && <p className="pid-port-warning" role="status">Services indisponibles : {conventionsError}</p>}
      {serviceDefinition(conventions, connection.service) && <p className="pid-selected-service"><i aria-hidden="true" style={{ backgroundColor: serviceDefinition(conventions, connection.service)!.color }} /><code>{serviceCode(conventions, connection.service) || '—'}</code>{serviceDefinition(conventions, connection.service)!.label}</p>}
      <p className="small-muted">Couleur et code suivent la convention du projet. Le service est déclaré, sans déduction de température ni effet sur le modèle physique.</p>
      {endpoint('source')}{endpoint('target')}
      <label className="check-label"><input type="checkbox" disabled={locked} checked={connection.directed} onChange={event => change({ directed: event.target.checked })} />Afficher la direction</label>
      <p className="small-muted">Cette ligne décrit le P&ID. Elle ne modifie pas les groupes de débit du modèle.</p>
      <button className="danger-text" disabled={locked} onClick={() => { onChange(project => ({ ...project, connections: project.connections.filter(connection => connection.id !== id) })); onClose(); }}><Unlink size={15} />Supprimer la liaison</button>
    </div></>;
}

function Inspector({ equipment, project, state, catalog, locked, online, unavailable, onChange, onError, onSnapshot, onClose, showForces = true }: Props & { equipment: Equipment; onClose: () => void; showForces?: boolean }) {
  const item = catalog.find(item => item.type === equipment.type);
  const documentary = equipment.type === 'pid_symbol';
  const modelled = physicalMultiport(equipment.type);
  const definition = drawingDefinition(catalog.find(item => item.type === 'pid_symbol')?.symbols ?? [], equipment);
  const [faultKind, setFaultKind] = useState(FAULTS[equipment.type]?.[0]?.key ?? '');
  const [faultValue, setFaultValue] = useState(equipment.type === 'heat_exchanger' ? '50' : '');
  const [busy, setBusy] = useState(false);
  const change = (patch: Partial<Equipment>) => onChange(project => ({ ...project, equipment: project.equipment.map(entry => entry.id === equipment.id ? { ...entry, ...patch } : entry) }));
  const faults = state?.faults[equipment.id] ?? {};
  const waitingForCycle = state?.guided_steps?.at(-1)?.state === 'queued';
  const createTags = () => {
    if (!item) return;
    const bindings = { ...equipment.bindings };
    const tags: Tag[] = [];
    Object.entries(item.ports).forEach(([port, spec]) => {
      if (bindings[port]) return;
      if (equipment.type === 'heat_exchanger' && spec.direction === 'output' || equipment.type === 'valve_three_way' && port === 'manual_request') return;
      const dataType = spec.data_types[0] as Tag['data_type'];
      const id = uid(`${equipment.id}_${port}`);
      const unit = spec.unit ?? '';
      const temperature = equipment.type === 'heat_exchanger' && ['primary_temperature', 'secondary_temperature'].includes(port);
      const heat = equipment.type === 'heat_exchanger' && port === 'heat';
      const initial = equipment.type === 'valve_three_way' && ['command', 'position'].includes(port) ? Number(equipment.params[port === 'command' ? 'demo_command' : 'initial_position_pct'] ?? 50) : temperature ? Number(equipment.params[port === 'primary_temperature' ? 'initial_primary_temperature_c' : 'initial_secondary_temperature_c'] ?? (port === 'primary_temperature' ? 80 : 20)) : 0;
      const heatBound = 600 * Number(equipment.params.ua_kw_k ?? 5);
      tags.push({ id, name: `${equipment.name}.${port}`, direction: spec.direction, data_type: dataType, unit, initial_value: dataType === 'BOOL' ? false : initial, min: dataType === 'BOOL' ? null : temperature ? -100 : heat ? -heatBound : 0, max: temperature ? 500 : heat ? heatBound : unit === '%' ? 100 : modelled && unit === 'L/s' ? 100000 : null, node_id: '', writable: spec.direction === 'input' });
      bindings[port] = id;
    });
    if (project.tags.length + tags.length > 200) { onError('Ces variables dépasseraient la limite de 200 tags par projet.'); return; }
    onChange(project => ({ ...project, tags: [...project.tags, ...tags], equipment: project.equipment.map(entry => entry.id === equipment.id ? { ...entry, bindings } : entry) }));
  };
  const mutate = async (path: string, method: string, body?: unknown) => {
    if (waitingForCycle) return;
    setBusy(true);
    try { onSnapshot(await api<Snapshot>(path, method, body)); } catch (error) { onError(String(error instanceof Error ? error.message : error)); } finally { setBusy(false); }
  };
  const renderParameter = ([key, value]: [string, string | number | boolean]) => {
    const spec = item?.parameters[key];
    const label = spec?.label ?? key;
    const tankReference = key === 'tank_id' || key.endsWith('_tank_id');
    const flowSource = key.endsWith('_flow_equipment');
    const flowField = key.endsWith('_flow_field');
    const sourceId = String(equipment.params[key.replace('_flow_field', '_flow_equipment')] ?? '');
    const source = project.equipment.find(entry => entry.id === sourceId);
    const references = project.equipment.filter(entry => entry.id !== equipment.id && (tankReference ? entry.type === 'tank' : flowSource ? FLOW_SOURCES.includes(entry.type) : entry.type !== 'pid_symbol'));
    const reference = tankReference || flowSource || key === 'source_equipment';
    const fields = source?.type === 'valve_three_way' ? ['flow_l_s', 'flow_a_l_s', 'flow_b_l_s'] : ['flow_l_s'];
    const options = flowField ? fields.map(field => ({ value: field, label: field === 'flow_a_l_s' ? 'Débit branche A' : field === 'flow_b_l_s' ? 'Débit branche B' : 'Débit total' })) : equipment.type === 'valve_three_way' && key === 'mode' ? [{ value: 'diverting', label: 'Dérivation AB → A + B' }, { value: 'mixing', label: 'Mélange A + B → AB' }] : spec?.options;
    const sourceConflict = flowSource && Boolean(value && equipment.bindings[key.replace('_flow_equipment', '_flow_command')]);
    return <label key={key} className={typeof value === 'boolean' ? 'check-label' : ''}>
      {typeof value !== 'boolean' && <span>{label}{spec?.unit && <small>{spec.unit === 'degC' ? '°C' : spec.unit}</small>}</span>}
      {typeof value === 'boolean' ? <><input aria-label={label} type="checkbox" disabled={locked} checked={value} onChange={event => change({ params: { ...equipment.params, [key]: event.target.checked } })} />{label}</>
        : reference ? <select aria-label={label} disabled={locked} value={String(value)} aria-invalid={sourceConflict || Boolean(value && !references.some(entry => entry.id === value))} onChange={event => {
          const params = { ...equipment.params, [key]: event.target.value };
          if (flowSource && project.equipment.find(entry => entry.id === event.target.value)?.type !== 'valve_three_way') params[key.replace('_flow_equipment', '_flow_field')] = 'flow_l_s';
          change({ params });
        }}><option value="">{flowSource ? 'Débit constant ou commande PLC' : '— Choisir —'}</option>{value && !references.some(entry => entry.id === value) && <option value={String(value)}>{String(value)} · à vérifier</option>}{references.map(entry => <option key={entry.id} value={entry.id}>{entry.name}</option>)}</select>
          : options ? <select aria-label={label} disabled={locked || flowField && !sourceId} value={String(value)} onChange={event => change({ params: { ...equipment.params, [key]: event.target.value } })}>{!options.some(option => (typeof option === 'string' ? option : option.value) === String(value)) && <option value={String(value)}>{String(value)} · à vérifier</option>}{options.map(option => <option key={typeof option === 'string' ? option : option.value} value={typeof option === 'string' ? option : option.value}>{typeof option === 'string' ? option : option.label}</option>)}</select>
            : <input aria-label={label} disabled={locked} type={typeof value === 'number' ? 'number' : 'text'} step="any" min={spec?.min} max={spec?.max} value={String(value)} onChange={event => change({ params: { ...equipment.params, [key]: typeof value === 'number' ? Number(event.target.value) : event.target.value } })} />}
      {sourceConflict && <span className="inline-error">Choisissez une source de débit ou une commande PLC pour ce circuit, puis retirez l’autre association.</span>}
    </label>;
  };
  const parameters = Object.entries({ ...item?.default_params, ...equipment.params });
  return <>
    <div className="panel-title"><span>{equipment.name}</span><button className="icon-button" onClick={onClose} aria-label="Fermer les propriétés"><X size={16} /></button></div>
    <div className="inspector-body">
      <span className="type-label">{documentary ? definition?.label ?? item?.label : item?.label ?? TYPE_LABELS[equipment.type]}</span>
      <label>Nom / repère<input disabled={locked} value={equipment.name} onChange={event => change({ name: event.target.value })} /></label>
      <label>Description<input disabled={locked} value={equipment.description ?? ''} placeholder="Fonction dans le procédé" onChange={event => change({ description: event.target.value })} /></label>
      {!documentary && <label>Unité d’affichage<input disabled={locked} value={equipment.unit ?? ''} placeholder="%, L, bar…" onChange={event => change({ unit: event.target.value })} /></label>}

      {documentary && <section className="pid-documentary-details" aria-label="Symbole documentaire">
        <strong>Non simulé</strong><p>Ce symbole décrit le dessin. Aucun débit, température, mélange ou état physique n’est calculé.</p>
        {definition?.instrument_code && <p>Code d’instrumentation : <code>{definition.instrument_code}</code>. Le numéro de boucle et le repère restent à définir dans la convention du projet.</p>}
        {definition?.source && <p className="pid-symbol-source">Symbole adapté de <a href={/^https?:\/\//i.test(definition.source.url) ? definition.source.url : undefined} target="_blank" rel="noopener noreferrer">{definition.source.name}</a> · licence {definition.source.license}. {definition.source.changes}</p>}
        {definition?.references?.length ? <p className="small-muted">Références de vocabulaire : {definition.references.join(', ')}. La source et la portée sont consultables dans le catalogue P&ID.</p> : null}
        {equipment.source_kind && <p className="pid-source-kind">Type source conservé : <span>{equipment.source_kind}</span></p>}
        <label>Rotation du symbole<select disabled={locked} value={equipment.rotation ?? 0} onChange={event => change({ rotation: Number(event.target.value) as PidRotation })}>{[0, 90, 180, 270].map(rotation => <option key={rotation} value={rotation}>{rotation}°</option>)}</select></label>
        <h4>{definition?.ports.length ?? 0} piquages documentaires</h4>
        {definition?.ports.map(port => <div className="pid-terminal-description" key={port.id}><code>{portLabel(port.id)}{portLabel(port.id) !== port.id && <small> · {port.id}</small>}</code><span>{port.label}</span></div>)}
        {definition?.ports.some(port => port.id.startsWith('primary_')) && <p>Les circuits primaire et secondaire restent distincts. Les quatre piquages n’établissent aucun transfert thermique.</p>}
        {definition?.ports.some(port => port.id === 'AB') && <p>AB est le raccord commun ; A et B sont les branches. Le sens et la fonction de mélange ou de diversion restent à vérifier sur le plan.</p>}
      </section>}

      {modelled && <section className="pid-model-details" aria-label="Modèle physique simplifié"><strong>Modèle simulé</strong>
        {equipment.type === 'heat_exchanger' ? <p>Deux circuits liquides mélangés, à volumes constants. Les conditions d’entrée et les sources de débit se règlent ci-dessous. Les tuyaux du dessin n’imposent aucun débit.</p> : <p>AB est le raccord commun. À 0 %, tout le débit passe par B ; à 100 %, par A. Les trois cuves choisies déterminent le transfert en mélange ou en dérivation.</p>}
        <label>Rotation du symbole<select disabled={locked} value={equipment.rotation ?? 0} onChange={event => change({ rotation: Number(event.target.value) as PidRotation })}>{[0, 90, 180, 270].map(rotation => <option key={rotation} value={rotation}>{rotation}°</option>)}</select></label>
        <PhysicalReadings equipment={equipment} state={state?.equipment[equipment.id] ?? {}} unavailable={Boolean(unavailable)} />
        {equipment.type === 'heat_exchanger' && <p>Puissance positive : transfert du primaire vers le secondaire ; négative : transfert inverse. Aucun changement de phase ni calcul de pression.</p>}
      </section>}

      <AnimationEditor equipment={equipment} project={project} state={state} locked={locked} onChange={animation => change({ animation })} />

      {!documentary && <><h4>Paramètres du modèle</h4>
      {equipment.type === 'heat_exchanger' ? <>{['primary', 'secondary', 'shared'].map(group => <fieldset className="pid-parameter-group" key={group}><legend>{group === 'primary' ? 'Circuit primaire' : group === 'secondary' ? 'Circuit secondaire' : 'Échange thermique'}</legend>{parameters.filter(([key]) => group === 'shared' ? !key.includes('primary') && !key.includes('secondary') : key.includes(group)).map(renderParameter)}</fieldset>)}</> : parameters.map(renderParameter)}

      <h4>Variables associées</h4>
      <p className="small-muted">Entrée = capteur vers PLC.<br />Sortie = commande du PLC.</p>
      {equipment.type === 'heat_exchanger' && <p className="small-muted">Les commandes PLC de débit et de température sont facultatives et remplacent les constantes correspondantes. Le bouton de création prépare uniquement les mesures simulées.</p>}
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
          {equipment.type === 'heat_exchanger' && port.endsWith('_flow_command') && tagId && equipment.params[port.replace('_flow_command', '_flow_equipment')] && <p className="inline-error">Une source de débit est déjà choisie pour ce circuit. Retirez cette source ou cette commande PLC.</p>}
          {tag && <div className="binding-value"><span>{tag.data_type}</span><strong>{fmt(state?.tags[tag.id]?.value ?? tag.initial_value)} {tag.unit}</strong></div>}
          {showForces && tag?.direction === 'input' && state?.run_id && <ForceField key={tag.id} tag={tag} state={state} unavailable={unavailable ?? (incompatible ? 'Associez une variable compatible avant de forcer la mesure.' : undefined)} onError={onError} onSnapshot={onSnapshot} />}
        </div>;
      })}
      {!locked && <button className="button compact-button full-width" onClick={createTags} disabled={project.tags.length >= 200}><WandSparkles size={14} />Créer les tags manquants</button>}
      </>}

      {(FAULTS[equipment.type]?.length ?? 0) > 0 && <>
        <h4>Injection de défaut</h4>
        {waitingForCycle && <p className="small-muted">STEP en attente du cycle d’échange. Commandes I/O temporairement suspendues.</p>}
        <select aria-label="Type de défaut" value={faultKind} onChange={event => { setFaultKind(event.target.value); setFaultValue(event.target.value === 'fouling' ? '50' : ''); }}>{FAULTS[equipment.type]?.map(fault => <option key={fault.key} value={fault.key}>{fault.label}</option>)}</select>
        {faultKind === 'fouling' && <label>Perte d’échange thermique (%)<input type="number" min="0" max="100" step="any" value={faultValue} onChange={event => setFaultValue(event.target.value)} /><small>100 % annule l’échange entre les circuits.</small></label>}
        {['out_of_range', 'valve_stuck'].includes(faultKind) && <label>Valeur {faultKind === 'valve_stuck' ? 'de position (%)' : 'hors plage'}<input type="number" step="any" value={faultValue} placeholder={faultKind === 'valve_stuck' ? '0' : '120'} onChange={event => setFaultValue(event.target.value)} /></label>}
        <div className="button-row"><button className="button warning-button compact-button" disabled={!online || !state?.run_id || !['running', 'paused'].includes(state.status) || state.scenario.state === 'completed' || busy || waitingForCycle || faultKind === 'fouling' && (faultValue === '' || !Number.isFinite(Number(faultValue)) || Number(faultValue) < 0 || Number(faultValue) > 100)} onClick={() => void mutate('/fault', 'POST', { equipment_id: equipment.id, kind: faultKind, ...(faultValue !== '' ? { value: Number(faultValue) } : {}) })}><Zap size={14} />Injecter</button>
          <button className="button compact-button" disabled={!online || !Object.keys(faults).length || busy || waitingForCycle} onClick={() => void mutate(`/fault/${encodeURIComponent(equipment.id)}`, 'DELETE')}><RotateCcw size={14} />Lever</button></div>
        {Object.keys(faults).length > 0 && <div className="active-faults">{Object.keys(faults).map(key => <span key={key}>{FAULTS[equipment.type]?.find(fault => fault.key === key)?.label ?? key}</span>)}</div>}
        {!state?.run_id && <p className="small-muted">Démarrez un essai pour injecter un défaut.</p>}
      </>}
      <div className="inspector-footer"><span className="mono">{equipment.id}</span><button className="danger-text" disabled={locked} onClick={() => { if (window.confirm(`Supprimer ${equipment.name} et ses liaisons graphiques ? Ses tags seront conservés.`)) { onChange(project => ({ ...project, equipment: project.equipment.filter(entry => entry.id !== equipment.id), connections: project.connections.filter(connection => connection.source !== equipment.id && connection.target !== equipment.id) })); onClose(); } }}><Trash2 size={14} />Supprimer</button></div>
    </div>
  </>;
}

export default function PidCanvas(props: Props) { return <ReactFlowProvider><Canvas {...props} /></ReactFlowProvider>; }
