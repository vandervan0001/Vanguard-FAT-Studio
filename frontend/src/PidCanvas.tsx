import { memo, useCallback, useMemo, useState } from 'react';
import {
  ReactFlow, ReactFlowProvider, Background, BackgroundVariant, Controls, MiniMap,
  Handle, Position, MarkerType, useReactFlow,
  type Node, type NodeProps, type NodeChange, type EdgeChange, type Connection,
} from '@xyflow/react';
import { CircleHelp, GripVertical, Plus, Trash2, Unlink, WandSparkles, X, Zap, RotateCcw, LockKeyhole } from 'lucide-react';
import { api } from './api';
import { fmt, uid, type CatalogItem, type Equipment, type EquipmentType, type Project, type Snapshot, type Scalar, type Tag } from './types';

type Props = {
  project: Project; state: Snapshot | null; catalog: CatalogItem[]; locked: boolean; online: boolean;
  onChange: (update: (project: Project) => Project) => void;
  onError: (message: string) => void; onSnapshot: (state: Snapshot) => void;
};
type EquipmentNode = Node<{ equipment: Equipment; state: Record<string, unknown>; tags: Snapshot['tags']; faults: Record<string, unknown>; locked: boolean }, 'equipment'>;

const TYPE_LABELS: Record<EquipmentType, string> = { tank: 'Cuve', pump: 'Pompe', valve_onoff: 'Vanne TOR', valve_control: 'Vanne modulante', analog_sensor: 'Capteur analogique', digital_sensor: 'Capteur binaire', indicator: 'Indicateur' };
const PREFIX: Record<EquipmentType, string> = { tank: 'TK', pump: 'P', valve_onoff: 'XV', valve_control: 'CV', analog_sensor: 'AI', digital_sensor: 'DI', indicator: 'ST' };
const FAULTS: Partial<Record<EquipmentType, { key: string; label: string }[]>> = {
  pump: [{ key: 'motor_trip', label: 'Défaut moteur' }],
  valve_onoff: [{ key: 'valve_stuck', label: 'Vanne bloquée' }],
  valve_control: [{ key: 'valve_stuck', label: 'Vanne bloquée' }],
  analog_sensor: [{ key: 'sensor_stuck', label: 'Capteur figé' }, { key: 'out_of_range', label: 'Signal hors plage' }],
  digital_sensor: [{ key: 'sensor_stuck', label: 'Capteur figé' }],
};

export function ProcessSymbol({ type, active = false, level = 40, compact = false }: { type: EquipmentType; active?: boolean; level?: number; compact?: boolean }) {
  const stroke = active ? '#0a907d' : '#61798c';
  const clampedLevel = Math.min(100, Math.max(0, level));
  return <svg className={`process-symbol ${compact ? 'compact' : ''}`} viewBox="0 0 100 85" fill="none" aria-hidden="true">
    {type === 'tank' ? <>
      <path d="M24 14 Q50 1 76 14 V67 Q50 80 24 67 Z" fill="#f7fafc" stroke={stroke} strokeWidth="2.5" />
      <svg x="25.5" y="13" width="49" height="57" viewBox="0 0 49 57" overflow="hidden">
        <rect x="0" y={57 - clampedLevel * .57} width="49" height={clampedLevel * .57} fill="#b9e8df" />
        <path d={`M0 ${57 - clampedLevel * .57} Q12 ${53 - clampedLevel * .57} 24 ${57 - clampedLevel * .57} T49 ${57 - clampedLevel * .57}`} stroke="#0b9b86" strokeWidth="1.8" />
      </svg>
      <path d="M24 14 Q50 27 76 14 M24 67 Q50 80 76 67 M24 42 H7 M76 57 H93 M34 74 V81 M66 74 V81" stroke={stroke} strokeWidth="2.5" />
      {[25, 34, 43, 52, 61].map(y => <path key={y} d={`M69 ${y} H74`} stroke="#6a938f" />)}
    </> : type === 'pump' ? <>
      <path d="M4 43 H29 M72 43 H96 M39 65 L32 76 H69 L61 65" stroke={stroke} strokeWidth="3" strokeLinejoin="round" />
      <circle cx="50" cy="43" r="23" fill={active ? '#e4f5ef' : '#f7fafc'} stroke={stroke} strokeWidth="2.5" />
      <path d="M40 27 L67 43 L40 59 Z" fill={active ? '#13a28a' : '#a4b4c0'} />
    </> : type === 'valve_onoff' || type === 'valve_control' ? <>
      <path d="M4 52 H24 M76 52 H96 M50 50 V22" stroke={stroke} strokeWidth="2.5" />
      <path d="M24 36 L76 68 V36 L24 68 Z" fill={active ? '#d2f1e7' : '#f7fafc'} stroke={stroke} strokeWidth="2.5" strokeLinejoin="round" />
      {type === 'valve_control' ? <path d="M33 23 A17 13 0 0 1 67 23 Z" fill="#e7f0f4" stroke={stroke} strokeWidth="2.5" /> : <rect x="38" y="11" width="24" height="16" rx="2" fill="#e7f0f4" stroke={stroke} strokeWidth="2.5" />}
    </> : <>
      <path d="M50 64 V81" stroke={stroke} strokeWidth="2" strokeDasharray={type === 'indicator' ? '3 3' : undefined} />
      <circle cx="50" cy="39" r="25" fill={active ? '#e4f5ef' : '#f7fafc'} stroke={stroke} strokeWidth="2.5" />
      <path d="M26 39 H74" stroke={stroke} strokeWidth="1.5" />
      <text x="50" y="34" textAnchor="middle" fill={stroke} fontSize="13" fontWeight="700">{type === 'analog_sensor' ? 'AI' : type === 'digital_sensor' ? 'DI' : 'ST'}</text>
      <text x="50" y="55" textAnchor="middle" fill={stroke} fontSize="11">{type === 'analog_sensor' ? '4–20' : type === 'digital_sensor' ? '0 / 1' : 'PLC'}</text>
    </>}
  </svg>;
}

const SymbolNode = memo(function SymbolNode({ data, selected }: NodeProps<EquipmentNode>) {
  const { equipment, state, tags, faults } = data;
  const primaryPort = equipment.type === 'tank' ? 'level' : equipment.type === 'pump' ? 'feedback' : equipment.type.startsWith('valve') ? 'position' : 'value';
  const portValue = tags[equipment.bindings[primaryPort]]?.value;
  const value = portValue ?? state[equipment.type === 'pump' ? 'running' : primaryPort] ?? state.value;
  const physicalValue = equipment.type.startsWith('valve') ? state.position ?? value : state.running ?? value;
  const active = typeof physicalValue === 'boolean' ? physicalValue : typeof physicalValue === 'number' && physicalValue > 0;
  const faulted = Object.keys(faults).length > 0 || Boolean(state.fault);
  const forced = Object.values(equipment.bindings).some(id => tags[id]?.forced);
  const unit = primaryPort === 'level' || primaryPort === 'position' ? '%' : equipment.unit;
  return <div className={`equipment-node ${equipment.type === 'tank' ? 'tank-node' : ''} ${selected ? 'selected' : ''} ${faulted ? 'faulted' : ''} ${forced ? 'forced-node' : ''}`}>
    <Handle type="target" position={Position.Left} isConnectable={!data.locked} />
    <div className="node-label"><span>{equipment.name}</span>{faulted ? <span className="node-alert">DÉFAUT</span> : forced ? <span className="node-force">FORCÉ</span> : null}</div>
    <ProcessSymbol type={equipment.type} active={active} level={Number(state.level_percent ?? state.level ?? value ?? equipment.params.initial_level_pct ?? 0)} />
    <div className={`node-value ${active ? 'is-active' : ''}`}>{value === undefined ? TYPE_LABELS[equipment.type] : `${fmt(value)}${typeof value === 'number' && unit ? ' ' + unit : ''}`}</div>
    <Handle type="source" position={Position.Right} isConnectable={!data.locked} />
  </div>;
});
const nodeTypes = { equipment: SymbolNode };

function Canvas({ project, state, catalog, locked, online, onChange, onError, onSnapshot }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [snapToGrid, setSnapToGrid] = useState(true);
  const [measurements, setMeasurements] = useState<Record<string, { width: number; height: number }>>({});
  const { screenToFlowPosition, fitView } = useReactFlow();
  const selected = project.equipment.find(equipment => equipment.id === selectedId);
  const nodes = useMemo<EquipmentNode[]>(() => project.equipment.map(equipment => ({
    id: equipment.id, type: 'equipment', position: equipment.position, measured: measurements[equipment.id], selected: selectedId === equipment.id,
    data: { equipment, state: state?.equipment[equipment.id] ?? {}, tags: state?.tags ?? {}, faults: state?.faults[equipment.id] ?? {}, locked },
  })), [project.equipment, state?.equipment, state?.tags, state?.faults, selectedId, locked, measurements]);
  const edges = useMemo(() => project.connections.map(connection => ({
    ...connection, type: 'smoothstep', selected: selectedEdge === connection.id,
    animated: state?.status === 'running',
    style: { stroke: selectedEdge === connection.id ? '#ed8140' : '#73969f', strokeWidth: 2 },
    ...(connection.directed ? { markerEnd: { type: MarkerType.ArrowClosed, color: '#73969f', width: 16, height: 16 } } : {}),
    labelStyle: { fill: '#516570', fontSize: 11 }, labelBgStyle: { fill: '#f5f8fa', fillOpacity: .95 },
  })), [project.connections, selectedEdge, state?.status]);

  const addEquipment = (type: EquipmentType, position?: { x: number; y: number }) => {
    if (locked) return;
    if (project.equipment.length >= 50) { onError('Le projet est limité à 50 équipements.'); return; }
    const item = catalog.find(item => item.type === type);
    if (!item) return;
    const id = uid(type);
    const count = project.equipment.filter(equipment => equipment.type === type).length + 101;
    onChange(project => ({ ...project, equipment: [...project.equipment, {
      id, type, name: `${PREFIX[type]}-${count}`, description: '', unit: '',
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
    if (project.connections.some(edge => edge.source === connection.source && edge.target === connection.target)) return;
    if (project.connections.length >= 200) { onError('Le projet est limité à 200 liaisons.'); return; }
    onChange(project => ({ ...project, connections: [...project.connections, { id: uid('line'), source: connection.source, target: connection.target, label: '', directed: true }] }));
  };

  return <div className="workbench">
    <aside className="palette panel">
      <div className="panel-title">Bibliothèque <span className="subtle-count">07</span></div>
      <p className="panel-hint">Glissez un équipement<br />sur le P&ID.</p>
      <div className="palette-items">
        {catalog.map(item => <button key={item.type} className="palette-item" draggable={!locked && project.equipment.length < 50} disabled={locked || project.equipment.length >= 50}
          onDragStart={event => { event.dataTransfer.setData('application/fat-equipment', item.type); event.dataTransfer.effectAllowed = 'move'; }}
          onClick={() => addEquipment(item.type)} title={`${item.description}\nCliquer ou glisser pour ajouter`}>
          <ProcessSymbol type={item.type} compact /><span>{item.label}</span><GripVertical size={13} className="drag-hint" />
        </button>)}
      </div>
      <div className="palette-note"><CircleHelp size={15} /><p>Reliez les points latéraux pour dessiner une conduite.</p></div>
      <label className="check-label grid-choice"><input type="checkbox" checked={snapToGrid} onChange={event => setSnapToGrid(event.target.checked)} />Aligner sur la grille</label>
      <div className="keyboard-help"><kbd>Suppr</kbd> supprimer<br /><kbd>Molette</kbd> zoomer<br /><kbd>Glisser fond</kbd> déplacer</div>
    </aside>

    <div className="canvas-area" onDragOver={event => { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; }}
      onDrop={event => { event.preventDefault(); const type = event.dataTransfer.getData('application/fat-equipment') as EquipmentType; if (catalog.some(item => item.type === type)) addEquipment(type, screenToFlowPosition({ x: event.clientX, y: event.clientY })); }}>
      <div className="canvas-topline"><span><span className={`small-dot ${locked ? 'green' : ''}`} />{locked ? 'SUPERVISION' : 'ÉDITION DU PROCÉDÉ'}</span><button onClick={() => fitView({ padding: .08, duration: 200 })}>Centrer le P&ID</button></div>
      {locked && <div className="editing-locked"><LockKeyhole size={13} />Édition verrouillée pendant l’essai</div>}
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes}
        onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
        onNodeClick={(_, node) => { setSelectedId(node.id); setSelectedEdge(null); }}
        onPaneClick={() => { setSelectedId(null); setSelectedEdge(null); }}
        nodesDraggable={!locked} nodesConnectable={!locked} deleteKeyCode={locked ? null : ['Backspace', 'Delete']}
        snapToGrid={snapToGrid} snapGrid={[20, 20]} minZoom={.25} maxZoom={2.5}
        fitView fitViewOptions={{ padding: .08 }} proOptions={{ hideAttribution: false }}
        ariaLabelConfig={{ 'controls.zoomIn.ariaLabel': 'Zoom avant', 'controls.zoomOut.ariaLabel': 'Zoom arrière', 'controls.fitView.ariaLabel': 'Centrer le P&ID', 'controls.interactive.ariaLabel': 'Verrouiller le canevas' }}>
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#cbd5dc" />
        <Controls showInteractive={false} />
        <MiniMap style={{ width: 120, height: 80 }} ariaLabel="Vue d’ensemble du P&ID" pannable zoomable nodeColor={node => node.selected ? '#ef8c52' : '#91b5b8'} maskColor="rgba(242,246,248,.6)" />
      </ReactFlow>
      {!project.equipment.length && <div className="canvas-empty"><div className="empty-cross"><Plus size={30} /></div><h3>Votre premier procédé</h3><p>Ajoutez une cuve, une pompe ou un instrument<br />depuis la bibliothèque à gauche.</p></div>}
      <div className="canvas-caption"><span>{project.equipment.length} équipements · {project.connections.length} liaisons</span><span>Modèle de procédé simplifié</span></div>
    </div>

    <aside className="inspector panel">
      {selected ? <Inspector key={selected.id} equipment={selected} project={project} state={state} catalog={catalog} locked={locked} online={online} onChange={onChange} onError={onError} onSnapshot={onSnapshot} onClose={() => setSelectedId(null)} />
        : selectedEdge ? <ConnectionInspector project={project} id={selectedEdge} locked={locked} onChange={onChange} onClose={() => setSelectedEdge(null)} />
          : <><div className="panel-title">Propriétés</div><div className="inspector-empty"><ProcessSymbol type="tank" /><h3>Sélectionnez un équipement</h3><p>Ses paramètres, ses variables PLC et ses défauts de simulation apparaîtront ici.</p></div><div className="model-note"><strong>Débits et liaisons</strong><p>Les conduites sont graphiques. Le débit est défini par la cuve cible, le sens et le groupe de débit de chaque pompe ou vanne.</p><p>Dans un même groupe, l’équipement le plus limitant fixe le débit. Les groupes indépendants s’additionnent.</p></div></>}
    </aside>
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

function Inspector({ equipment, project, state, catalog, locked, online, onChange, onError, onSnapshot, onClose }: Props & { equipment: Equipment; onClose: () => void }) {
  const item = catalog.find(item => item.type === equipment.type);
  const [faultKind, setFaultKind] = useState(FAULTS[equipment.type]?.[0]?.key ?? '');
  const [faultValue, setFaultValue] = useState('');
  const [busy, setBusy] = useState(false);
  const change = (patch: Partial<Equipment>) => onChange(project => ({ ...project, equipment: project.equipment.map(entry => entry.id === equipment.id ? { ...entry, ...patch } : entry) }));
  const faults = state?.faults[equipment.id] ?? {};
  const createTags = () => {
    if (!item) return;
    const bindings = { ...equipment.bindings };
    const tags: Tag[] = [];
    Object.entries(item.ports).forEach(([port, spec]) => {
      if (bindings[port]) return;
      const dataType = spec.data_types[0] as Tag['data_type'];
      const id = uid(`${equipment.id}_${port}`);
      const unit = spec.unit ?? '';
      tags.push({ id, name: `${equipment.name}.${port}`, direction: spec.direction, data_type: dataType, unit, initial_value: dataType === 'BOOL' ? false : 0, min: dataType === 'BOOL' ? null : 0, max: unit === '%' ? 100 : null, node_id: '', writable: spec.direction === 'input' });
      bindings[port] = id;
    });
    if (project.tags.length + tags.length > 200) { onError('Ces variables dépasseraient la limite de 200 tags par projet.'); return; }
    onChange(project => ({ ...project, tags: [...project.tags, ...tags], equipment: project.equipment.map(entry => entry.id === equipment.id ? { ...entry, bindings } : entry) }));
  };
  const mutate = async (path: string, method: string, body?: unknown) => {
    setBusy(true);
    try { onSnapshot(await api<Snapshot>(path, method, body)); } catch (error) { onError(String(error instanceof Error ? error.message : error)); } finally { setBusy(false); }
  };
  return <>
    <div className="panel-title"><span>{equipment.name}</span><button className="icon-button" onClick={onClose} aria-label="Fermer les propriétés"><X size={16} /></button></div>
    <div className="inspector-body">
      <span className="type-label">{item?.label ?? TYPE_LABELS[equipment.type]}</span>
      <label>Nom / repère<input disabled={locked} value={equipment.name} onChange={event => change({ name: event.target.value })} /></label>
      <label>Description<input disabled={locked} value={equipment.description ?? ''} placeholder="Fonction dans le procédé" onChange={event => change({ description: event.target.value })} /></label>
      <label>Unité d’affichage<input disabled={locked} value={equipment.unit ?? ''} placeholder="%, L, bar…" onChange={event => change({ unit: event.target.value })} /></label>

      <h4>Paramètres du modèle</h4>
      {Object.entries({ ...item?.default_params, ...equipment.params }).map(([key, value]) => {
        const spec = item?.parameters[key];
        const label = spec?.label ?? key;
        const isEquipment = key === 'tank_id' || key === 'source_equipment';
        const options = spec?.options;
        return <label key={key} className={typeof value === 'boolean' ? 'check-label' : ''}>
          {typeof value !== 'boolean' && <span>{label}{spec?.unit && <small>{spec.unit}</small>}</span>}
          {typeof value === 'boolean' ? <><input type="checkbox" disabled={locked} checked={value} onChange={event => change({ params: { ...equipment.params, [key]: event.target.checked } })} />{label}</>
            : isEquipment ? <select disabled={locked} value={String(value)} onChange={event => change({ params: { ...equipment.params, [key]: event.target.value } })}><option value="">— Choisir —</option>{project.equipment.filter(entry => entry.id !== equipment.id && (key !== 'tank_id' || entry.type === 'tank')).map(entry => <option key={entry.id} value={entry.id}>{entry.name}</option>)}</select>
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
          {tag?.direction === 'input' && state?.run_id && <ForceField key={tag.id} tag={tag} state={state} disabled={!online || incompatible} onError={onError} onSnapshot={onSnapshot} />}
        </div>;
      })}
      {!locked && <button className="button compact-button full-width" onClick={createTags} disabled={project.tags.length >= 200}><WandSparkles size={14} />Créer les tags manquants</button>}

      {(FAULTS[equipment.type]?.length ?? 0) > 0 && <>
        <h4>Injection de défaut</h4>
        <select aria-label="Type de défaut" value={faultKind} onChange={event => { setFaultKind(event.target.value); setFaultValue(''); }}>{FAULTS[equipment.type]?.map(fault => <option key={fault.key} value={fault.key}>{fault.label}</option>)}</select>
        {['out_of_range', 'valve_stuck'].includes(faultKind) && <label>Valeur {faultKind === 'valve_stuck' ? 'de position (%)' : 'hors plage'}<input type="number" step="any" value={faultValue} placeholder={faultKind === 'valve_stuck' ? '0' : '120'} onChange={event => setFaultValue(event.target.value)} /></label>}
        <div className="button-row"><button className="button warning-button compact-button" disabled={!online || !state?.run_id || !['running', 'paused'].includes(state.status) || state.scenario.state === 'completed' || busy} onClick={() => void mutate('/fault', 'POST', { equipment_id: equipment.id, kind: faultKind, ...(faultValue !== '' ? { value: Number(faultValue) } : {}) })}><Zap size={14} />Injecter</button>
          <button className="button compact-button" disabled={!online || !Object.keys(faults).length || busy} onClick={() => void mutate(`/fault/${encodeURIComponent(equipment.id)}`, 'DELETE')}><RotateCcw size={14} />Lever</button></div>
        {Object.keys(faults).length > 0 && <div className="active-faults">{Object.keys(faults).map(key => <span key={key}>{FAULTS[equipment.type]?.find(fault => fault.key === key)?.label ?? key}</span>)}</div>}
        {!state?.run_id && <p className="small-muted">Démarrez un essai pour injecter un défaut.</p>}
      </>}
      <div className="inspector-footer"><span className="mono">{equipment.id}</span><button className="danger-text" disabled={locked} onClick={() => { if (window.confirm(`Supprimer ${equipment.name} et ses liaisons graphiques ? Ses tags seront conservés.`)) { onChange(project => ({ ...project, equipment: project.equipment.filter(entry => entry.id !== equipment.id), connections: project.connections.filter(connection => connection.source !== equipment.id && connection.target !== equipment.id) })); onClose(); } }}><Trash2 size={14} />Supprimer</button></div>
    </div>
  </>;
}

export function ForceField({ tag, state, onSnapshot, onError, disabled = false }: { tag: Tag; state: Snapshot; disabled?: boolean; onSnapshot: Props['onSnapshot']; onError: Props['onError'] }) {
  const [value, setValue] = useState(String(state.tags[tag.id]?.value ?? tag.initial_value));
  const [busy, setBusy] = useState(false);
  const current = state.tags[tag.id];
  const inactive = disabled || !['running', 'paused'].includes(state.status) || state.scenario.state === 'completed';
  const apply = async (release = false) => {
    setBusy(true);
    try {
      if (!release && value.trim() === '') throw new Error('Saisissez une valeur avant de forcer la mesure.');
      const parsed: Scalar = tag.data_type === 'BOOL' ? value === 'true' : Number(value);
      if (!release && typeof parsed === 'number' && (!Number.isFinite(parsed) || (tag.data_type !== 'REAL' && !Number.isInteger(parsed)))) throw new Error('Saisissez une valeur numérique valide pour ce type.');
      onSnapshot(await api<Snapshot>(release ? `/force/${encodeURIComponent(tag.id)}` : '/force', release ? 'DELETE' : 'POST', release ? undefined : { tag_id: tag.id, value: parsed }));
    } catch (error) { onError(error instanceof Error ? error.message : String(error)); } finally { setBusy(false); }
  };
  return <div className={`force-field ${current?.forced ? 'active' : ''}`}>
    {tag.data_type === 'BOOL' ? <select aria-label={`Forçage ${tag.name}`} value={value} onChange={event => setValue(event.target.value)}><option value="false">FALSE</option><option value="true">TRUE</option></select>
      : <input type="number" step={tag.data_type === 'REAL' ? 'any' : '1'} min={tag.min ?? undefined} max={tag.max ?? undefined} aria-label={`Forçage ${tag.name}`} value={value} onChange={event => setValue(event.target.value)} />}
    <button disabled={inactive || busy || !tag.writable} onClick={() => void apply()} title={`Forcer ${tag.name}`}>{current?.forced ? 'Modifier' : 'Forcer'}</button>
    {current?.forced && <button disabled={inactive || busy} onClick={() => void apply(true)} title={`Libérer ${tag.name}`} aria-label={`Libérer ${tag.name}`}><RotateCcw size={13} /></button>}
  </div>;
}

export default function PidCanvas(props: Props) { return <ReactFlowProvider><Canvas {...props} /></ReactFlowProvider>; }
