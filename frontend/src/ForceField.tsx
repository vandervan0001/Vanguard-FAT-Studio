import { useRef, useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { api } from './api';
import { actionPreview, diagnosticLabel, diagnosticProfile, displayValue, engineeringUnit, nativeValue, stimulusUnits } from './signal';
import { fmt, type PreparedAction, type Scalar, type Snapshot, type Tag } from './types';

export function ForceField({ tag, state, onSnapshot, onError, disabled = false }: { tag: Tag; state: Snapshot; disabled?: boolean; onSnapshot: (state: Snapshot) => void; onError: (message: string) => void }) {
  const initialUnit = diagnosticProfile(tag, state.tags[tag.id]) ? 'native' : tag.signal ? 'engineering' : 'native';
  const [unit, setUnit] = useState<PreparedAction['unit']>(initialUnit);
  const [value, setValue] = useState(String(displayValue(tag, state.tags[tag.id]?.value ?? tag.initial_value, initialUnit)));
  const [diagnostic, setDiagnostic] = useState(false);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const current = state.tags[tag.id];
  const waitingForCycle = state.guided_steps?.at(-1)?.state === 'queued';
  const inactive = disabled || !['running', 'paused'].includes(state.status) || state.scenario.state === 'completed' || waitingForCycle;
  const parsed: Scalar = tag.data_type === 'BOOL' ? value === 'true' : Number(value);
  const prepared = { action: 'force' as const, target: tag.id, value: parsed, unit, diagnostic };
  let percentage = 0;
  let preparedProfile: ReturnType<typeof diagnosticProfile> = null;
  try {
    if (tag.signal) {
      const raw = nativeValue(tag, parsed, unit, diagnostic);
      preparedProfile = diagnostic ? diagnosticProfile(tag, { value: raw, quality: 'out_of_range' }) : null;
      if (!preparedProfile) percentage = Number(displayValue(tag, raw, 'percent'));
    }
  } catch { /* Invalid typed input stays editable; the server still validates the submitted stimulus. */ }
  const setPercentage = (percentage: number) => {
    if (!tag.signal) return;
    const raw = nativeValue(tag, percentage, 'percent');
    setValue(String(displayValue(tag, raw, unit)));
  };
  const apply = async (release = false, stimulus = prepared) => {
    if (busyRef.current || inactive || !state.run_id) return;
    busyRef.current = true; setBusy(true);
    try {
      if (!release && stimulus === prepared && value.trim() === '') throw new Error('Saisissez une valeur avant de forcer la mesure.');
      if (!release) nativeValue(tag, stimulus.value, stimulus.unit, stimulus.diagnostic);
      onSnapshot(await api<Snapshot>(release ? `/force/${encodeURIComponent(tag.id)}` : tag.data_type === 'BOOL' ? '/force' : '/force/stimulus', release ? 'DELETE' : 'POST', release ? undefined : { tag_id: tag.id, value: stimulus.value, ...(tag.data_type !== 'BOOL' ? { unit: stimulus.unit, diagnostic: stimulus.diagnostic } : {}) }, undefined, state.run_id));
    } catch (error) { onError(error instanceof Error ? error.message : String(error)); } finally { busyRef.current = false; setBusy(false); }
  };
  return <div className="force-control">
    {waitingForCycle && <small className="small-muted">STEP en attente du cycle d’échange. Commandes I/O temporairement suspendues.</small>}
    {tag.signal && <select className="force-unit" aria-label={`Unité de stimulus ${tag.name}`} disabled={inactive || busy} value={unit} onChange={event => { const next = event.target.value as PreparedAction['unit']; let raw = current?.value ?? tag.initial_value; try { raw = nativeValue(tag, parsed, unit, diagnostic); } catch { /* Start the new unit from the acquired value if the draft is invalid. */ } setUnit(next); setValue(String(displayValue(tag, raw, next))); }}>{stimulusUnits(tag).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select>}
    <div className={`force-field ${current?.forced ? 'active' : ''}`}>
      {tag.data_type === 'BOOL' ? <select disabled={inactive || busy} aria-label={`Forçage ${tag.name}`} value={value} onChange={event => setValue(event.target.value)}><option value="false">FALSE</option><option value="true">TRUE</option></select>
        : <input disabled={inactive || busy} type="number" step={unit !== 'native' || tag.data_type === 'REAL' ? 'any' : '1'} min={diagnostic ? undefined : unit === 'mA' ? 4 : unit === 'V' || unit === 'percent' ? 0 : unit === 'engineering' ? tag.signal?.engineering_min ?? 0 : tag.min ?? undefined} max={diagnostic ? undefined : unit === 'mA' ? 20 : unit === 'V' ? 10 : unit === 'percent' ? 100 : unit === 'engineering' ? tag.signal?.engineering_max ?? 100 : tag.max ?? undefined} aria-label={`Forçage ${tag.name}`} value={value} onChange={event => setValue(event.target.value)} />}
      <button disabled={inactive || busy || !tag.writable} onClick={() => void apply()} title={`Forcer ${tag.name}`}>{current?.forced ? 'Modifier' : 'Forcer'}</button>
      {current?.forced && <button disabled={inactive || busy} onClick={() => void apply(true)} title={`Libérer ${tag.name}`} aria-label={`Libérer ${tag.name}`}><RotateCcw size={13} /></button>}
    </div>
    {tag.signal && <><small className="conversion-preview">{value === '' ? 'Saisissez le stimulus' : actionPreview(tag, prepared)}</small><div className="stimulus-slider"><label htmlFor={`stimulus-range-${tag.id}`}>Plage nominale<span>{preparedProfile ? `${diagnosticLabel(preparedProfile)} · hors plage` : `${fmt(percentage, 1)} %`}</span></label><input id={`stimulus-range-${tag.id}`} aria-label={`Pourcentage ${tag.name}`} disabled={inactive || busy} type="range" min={0} max={100} step={.1} value={Math.max(0, Math.min(100, percentage))} onChange={event => setPercentage(Number(event.target.value))} /><div className="stimulus-presets">{[0, 25, 50, 100].map(percent => <button key={percent} disabled={inactive || busy} onClick={() => setPercentage(percent)} aria-label={`Préparer ${percent} % ${tag.name}`}>{percent} %</button>)}</div><small>{fmt(tag.signal.engineering_min ?? 0)} à {fmt(tag.signal.engineering_max ?? 100)} {engineeringUnit(tag)} ↔ {fmt(tag.signal.raw_min)} à {fmt(tag.signal.raw_max)} {tag.unit || 'brut'}</small></div></>}
    {tag.data_type !== 'BOOL' && <div className="stimulus-diagnostic"><label className="check-label"><input aria-label={`Diagnostic hors plage ${tag.name}`} type="checkbox" disabled={inactive || busy} checked={diagnostic} onChange={event => setDiagnostic(event.target.checked)} />Stimulus de diagnostic hors plage</label>{tag.signal?.kind === '4-20mA' && diagnostic && <><div className="button-row">{[0, 24].map(value => <button className="button compact-button" key={value} disabled={inactive || busy || !tag.writable} onClick={() => { setUnit('mA'); setValue(String(value)); void apply(false, { ...prepared, value, unit: 'mA', diagnostic: true }); }}>Injecter {value} mA</button>)}</div><small>Codes du profil : bas {fmt(tag.signal.underflow_raw)}, haut {fmt(tag.signal.overflow_raw)}. À qualifier pour le module testé.</small></>}</div>}
  </div>;
}
