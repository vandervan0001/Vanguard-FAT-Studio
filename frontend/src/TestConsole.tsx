import { useEffect, useRef, useState } from 'react';
import { ArrowDownLeft, LockKeyhole, Radio, RotateCcw } from 'lucide-react';
import { api } from './api';
import { ForceField } from './ForceField';
import { IoControl, IoPanelStatus, ioBlockReason, READ_ONLY_IO } from './IoAccess';
import { diagnosticLabel, diagnosticProfile, displayValue, electricalValue, engineeringUnit, signalUnit, tagReference } from './signal';
import { fmt, type Project, type Snapshot, type Tag } from './types';

type Controls = { project: Project; state: Snapshot | null; unavailable?: string; onSnapshot: (state: Snapshot) => void; onError: (message: string) => void };

type ContactKind = 'pushbutton' | 'switch' | 'contact';
const CONTACT_LABELS: Record<ContactKind, string> = { pushbutton: 'Poussoir', switch: 'Commutateur', contact: 'Contact' };

export function ContactSymbol({ kind = 'contact', closed = false }: { kind?: ContactKind; closed?: boolean }) {
  return <svg className={`contact-symbol ${closed ? 'closed' : ''}`} viewBox="0 0 64 48" fill="none" aria-hidden="true">
    <path d="M3 33H18M46 33H61" />
    <circle cx="19" cy="33" r="2.5" /><circle cx="45" cy="33" r="2.5" />
    <path className="contact-blade" d={closed ? 'M21 33H43' : 'M21 32L42 21'} />
    {kind === 'pushbutton' ? <><path d="M24 7H40M32 7V22M25 24H39" /><path d="M29 13H35M29 17H35" className="contact-spring" /></> : kind === 'switch' ? <><path d="M31 22V15L42 5" /><circle cx="44" cy="4" r="2.5" /></> : <path d="M32 7V23" strokeDasharray="3 3" />}
  </svg>;
}

function DigitalButton({ tag, state, unavailable, onSnapshot, onError, label, kind }: Omit<Controls, 'project'> & { tag: Tag; label: string; kind: ContactKind }) {
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [pulseUntil, setPulseUntil] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const live = state?.tags[tag.id];
  const closed = Boolean(live?.value ?? tag.initial_value);
  const pulsing = state?.pulses ? Boolean(state.pulses[tag.id]) : Boolean(live?.forced && (state?.sim_time_s ?? 0) < pulseUntil);
  const reason = tag.writable ? ioBlockReason(state, unavailable) : READ_ONLY_IO;
  const enabled = !reason;
  const cancel = () => { if (timer.current) clearTimeout(timer.current); timer.current = null; };
  useEffect(() => cancel, [state?.run_id, enabled]);
  const send = async (maintain: boolean) => {
    if (!enabled || busyRef.current || !state?.run_id) return;
    busyRef.current = true;
    setBusy(true);
    try {
      const release = maintain && live?.forced;
      const snapshot = await api<Snapshot>(release ? `/force/${encodeURIComponent(tag.id)}` : maintain ? '/force' : '/force/pulse',
        release ? 'DELETE' : 'POST', release ? undefined : { tag_id: tag.id, value: !closed, ...(!maintain ? { duration_ms: 300 } : {}) }, undefined, state.run_id);
      setPulseUntil(maintain ? 0 : snapshot.sim_time_s + .3);
      onSnapshot(snapshot);
    } catch (error) { onError(error instanceof Error ? error.message : String(error)); }
    finally { busyRef.current = false; setBusy(false); }
  };
  return <div className={`digital-control ${live?.forced ? 'maintained' : ''}`} data-tag={tag.id}>
    <IoControl target={tag.name} reason={reason}>
    <button className={`digital-push ${closed ? 'on' : ''} control-${kind}`} disabled={!enabled || busy}
      aria-label={`${CONTACT_LABELS[kind]} ${tag.name}`} aria-pressed={closed} title={`${tag.name} · ${tagReference(tag)}. Clic : impulsion de 300 ms après la fenêtre de double clic de 550 ms. Double clic : maintenir ou libérer.`}
      onClick={event => { if (event.detail > 1) return; cancel(); if (event.detail === 0) { void send(false); return; } timer.current = setTimeout(() => { timer.current = null; void send(false); }, 550); }}
      onDoubleClick={event => { event.preventDefault(); cancel(); void send(true); }}
      onKeyDown={event => { if (event.key === 'Escape') cancel(); }}>
      <ContactSymbol kind={kind} closed={closed} /><span className="digital-label"><strong>{label}</strong><small>{tagReference(tag)}</small><span>{pulsing ? 'Impulsion' : live?.forced ? 'Maintenu' : CONTACT_LABELS[kind]} · {live?.quality ?? 'Initial'}</span></span>
      <span className="contact-value"><i className="contact-led" />{closed ? '1' : '0'}</span>
    </button>
    {live?.forced && !pulsing && <button className="release-contact" disabled={!enabled || busy} aria-label={`Libérer le maintien ${tag.name}`} onClick={() => { cancel(); void send(true); }}><LockKeyhole size={11} />Libérer le maintien<RotateCcw size={11} /></button>}
    </IoControl>
  </div>;
}

export function DigitalInputs(props: Controls) {
  const tags = props.project.tags.filter(tag => tag.direction === 'input' && tag.data_type === 'BOOL');
  const [filter, setFilter] = useState('');
  const visible = tags.filter(tag => `${tag.id} ${tag.name} ${tagReference(tag)}`.toLocaleLowerCase().includes(filter.toLocaleLowerCase()));
  const equipmentFor = (tag: Tag) => props.project.equipment.find(item => item.bindings.value === tag.id);
  const label = (tag: Tag) => equipmentFor(tag)?.name.replace(/^[^·]*·\s*/, '') ?? tag.name;
  const kind = (tag: Tag): ContactKind => /^(PB\s*·)|pb$/i.test(`${equipmentFor(tag)?.name ?? ''} ${tag.id}`) ? 'pushbutton' : /^(Sélecteur|Manu)\s*·/i.test(equipmentFor(tag)?.name ?? '') || /_request$/.test(tag.id) ? 'switch' : 'contact';
  return <aside className="test-inputs digital-inputs panel" aria-label="Entrées digitales">
    <div className="panel-title"><span><Radio size={14} />Entrées digitales</span><span className="subtle-count">{filter ? `${visible.length} / ` : ''}{tags.length}</span></div>
    <div className="input-filter"><input type="search" aria-label="Filtrer les entrées digitales" placeholder="Repère ou variable…" value={filter} onChange={event => setFilter(event.target.value)} /></div>
    <IoPanelStatus reason={ioBlockReason(props.state, props.unavailable)}>
      Un clic donne une impulsion de 300 ms. Double-cliquez pour maintenir ou libérer.
    </IoPanelStatus>
    <div className="digital-controls">{visible.map(tag => <DigitalButton key={tag.id} tag={tag} label={label(tag)} kind={kind(tag)} {...props} />)}</div>
    {tags.length > 0 && !visible.length && <p className="panel-hint">Aucune entrée correspondante.</p>}
    {!tags.length && <p className="panel-hint">Aucune entrée digitale déclarée.</p>}
    <p className="input-footnote">Le clic souris attend 550 ms pour distinguer un double clic. L’impulsion inverse le contact pendant 300 ms simulées. Le serveur gère son retour, même si la vue se ferme.</p>
  </aside>;
}

export function AnalogInputs({ project, state, unavailable, onError, onSnapshot }: Controls) {
  const tags = project.tags.filter(tag => tag.direction === 'input' && tag.data_type !== 'BOOL');
  const [filter, setFilter] = useState('');
  const visible = tags.filter(tag => `${tag.id} ${tag.name} ${tagReference(tag)}`.toLocaleLowerCase().includes(filter.toLocaleLowerCase()));
  return <aside className="test-inputs analog-inputs panel" aria-label="Entrées analogiques">
    <div className="panel-title"><span><ArrowDownLeft size={15} />Entrées analogiques</span><span className="subtle-count">{filter ? `${visible.length} / ` : ''}{tags.length}</span></div>
    <div className="input-filter"><input type="search" aria-label="Filtrer les entrées analogiques" placeholder="Repère ou variable…" value={filter} onChange={event => setFilter(event.target.value)} /></div>
    <IoPanelStatus reason={ioBlockReason(state, unavailable, true)}>
      {state?.status === 'paused' ? 'Vous pouvez encore forcer une valeur en pause.' : 'Saisissez une valeur puis cliquez sur « Forcer ».'} Libérez-la pour reprendre la mesure simulée.
    </IoPanelStatus>
    <div className="analog-controls">{visible.map(tag => {
      const profile = diagnosticProfile(tag, state?.tags[tag.id]);
      return <div className={`analog-control ${state?.tags[tag.id]?.forced ? 'maintained' : ''} ${profile ? 'diagnostic-reading' : ''}`} key={tag.id} data-tag={tag.id}>
      <div className="analog-label"><strong>{tag.name}</strong><span>{tag.data_type}</span></div>
      <code>{tag.plc_address || tag.plc_symbol || (project.plc.mode === 'demo' ? 'Tag local de démonstration' : tag.node_id || 'NodeId à renseigner')}</code>
      <div className="analog-reading">{profile ? <><strong>{diagnosticLabel(profile)}</strong><small>Code du profil</small></> : <>{fmt(displayValue(tag, state?.tags[tag.id]?.value ?? tag.initial_value, tag.signal ? 'engineering' : 'native'), 2)}<small>{tag.signal ? engineeringUnit(tag) : tag.unit || tag.data_type}</small>{tag.signal && signalUnit(tag) !== 'native' && <span className="analog-electrical">{fmt(electricalValue(tag, state?.tags[tag.id]?.value ?? tag.initial_value), 2)} {signalUnit(tag)}</span>}</>}</div>
      {tag.signal && <div className="analog-native">Brut acquis : {fmt(state?.tags[tag.id]?.value ?? tag.initial_value, 2)} {tag.unit || tag.data_type}</div>}
      {state && <ForceField key={`${tag.id}-${tag.signal?.kind ?? 'native'}`} tag={tag} state={state} unavailable={unavailable} onSnapshot={onSnapshot} onError={onError} />}
      <div className="analog-range">{tag.min == null ? '…' : fmt(tag.min)} à {tag.max == null ? '…' : fmt(tag.max)} {tag.unit}<span>{state?.tags[tag.id]?.forced ? 'FORCÉ' : state?.tags[tag.id]?.quality ?? 'Initial'}</span></div>
    </div>; })}</div>
    {tags.length > 0 && !visible.length && <p className="panel-hint">Aucune entrée correspondante.</p>}
  </aside>;
}

export function PlcOutputs({ project, state }: Pick<Controls, 'project' | 'state'>) {
  const ids = new Set(project.equipment.filter(item => item.type === 'indicator').map(item => item.bindings.value));
  const tags = project.tags.filter(tag => tag.direction === 'output' && (ids.has(tag.id) || ['run_cmd', 'speed_cmd', 'complete'].includes(tag.id)));
  if (!tags.length) return null;
  return <div className="plc-output-strip" aria-label="Retours du PLC">{tags.map(tag => <div key={tag.id} className={state?.tags[tag.id]?.value ? 'active' : ''}><span>{tag.name}</span><strong>{fmt(state?.tags[tag.id]?.value ?? tag.initial_value)} {tag.unit}</strong></div>)}</div>;
}
