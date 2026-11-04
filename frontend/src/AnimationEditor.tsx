import { Activity } from 'lucide-react';
import { fmt, type Equipment, type EquipmentAnimation, type Project, type Snapshot, type Tag } from './types';
import { OPERATORS, tagOption } from './signal';

export function animationReading(animation: EquipmentAnimation, live: Snapshot['tags'][string] | undefined, dataType?: Tag['data_type']) {
  if (!live || ['initial', 'unknown'].includes(live.quality)) return { available: false, initial: true, active: false, percent: 0 };
  if (!['good', 'forced', 'out_of_range', 'fault'].includes(live.quality)) return { available: false, initial: false, active: false, percent: 0 };
  const actual = live.value;
  const expected = dataType === 'REAL' && typeof animation.value === 'number' ? Math.fround(animation.value) : animation.value;
  const equal = actual === expected;
  const active = animation.operator === 'eq' ? equal : animation.operator === 'ne' ? !equal : typeof actual !== 'number' || typeof expected !== 'number' ? false : animation.operator === 'gt' ? actual > expected : animation.operator === 'ge' ? actual >= expected : animation.operator === 'lt' ? actual < expected : actual <= expected;
  const percent = typeof actual === 'number' && animation.max > animation.min ? Math.max(0, Math.min(100, (actual - animation.min) / (animation.max - animation.min) * 100)) : actual ? 100 : 0;
  return { available: true, initial: false, active, percent };
}

export function AnimationEditor({ equipment, project, state, locked, onChange }: { equipment: Equipment; project: Project; state: Snapshot | null; locked: boolean; onChange: (animation: EquipmentAnimation | null) => void }) {
  const animation = equipment.animation;
  const tag = project.tags.find(tag => tag.id === animation?.tag_id);
  const patch = (update: Partial<EquipmentAnimation>) => { if (animation) onChange({ ...animation, ...update }); };
  const reading = animation ? animationReading(animation, state?.tags[animation.tag_id], tag?.data_type) : null;
  const enable = () => {
    const candidate = project.tags.find(tag => tag.direction === 'output' && Object.values(equipment.bindings).includes(tag.id)) ?? project.tags[0];
    if (candidate) onChange({ tag_id: candidate.id, operator: 'eq', value: candidate.data_type === 'BOOL' ? true : 0, effect: 'highlight', min: candidate.min ?? 0, max: candidate.max ?? 100, active_color: '#079c83', inactive_color: '#6d8291' });
  };
  return <section className="animation-editor">
    <h4><Activity size={13} />Animation par variable</h4>
    <label className="check-label"><input type="checkbox" disabled={locked || !project.tags.length} checked={Boolean(animation)} onChange={event => event.target.checked ? enable() : onChange(null)} />Lier l’apparence à un tag</label>
    <p className="small-muted">Lecture seule. Cette règle visuelle ne modifie ni les commandes PLC ni le modèle physique.</p>
    {animation && <>
      <label>Variable d’animation<select aria-label="Variable d’animation" disabled={locked} value={animation.tag_id} onChange={event => { const target = project.tags.find(tag => tag.id === event.target.value)!; patch({ tag_id: target.id, operator: 'eq', value: target.data_type === 'BOOL' ? true : 0, ...(target.data_type === 'BOOL' && ['level', 'position'].includes(animation.effect) ? { effect: 'highlight' } : {}), min: target.min ?? 0, max: target.max ?? 100 }); }}>{project.tags.map(tag => <option key={tag.id} value={tag.id}>{tagOption(tag)}</option>)}</select></label>
      <div className="animation-condition"><label>Condition active<select aria-label="Opérateur d’animation" disabled={locked} value={animation.operator} onChange={event => patch({ operator: event.target.value as EquipmentAnimation['operator'] })}>{Object.entries(OPERATORS).filter(([key]) => tag?.data_type !== 'BOOL' || ['eq', 'ne'].includes(key)).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>Valeur active{tag?.data_type === 'BOOL' ? <select aria-label="Valeur active de l’animation" disabled={locked} value={String(animation.value)} onChange={event => patch({ value: event.target.value === 'true' })}><option value="true">TRUE</option><option value="false">FALSE</option></select> : <input aria-label="Valeur active de l’animation" type="number" step="any" disabled={locked} value={Number(animation.value)} onChange={event => patch({ value: Number(event.target.value) })} />}</label></div>
      <label>Effet visuel<select aria-label="Effet visuel" disabled={locked} value={animation.effect} onChange={event => patch({ effect: event.target.value as EquipmentAnimation['effect'] })}><option value="highlight">Couleur</option><option value="pulse">Pulsation</option><option value="rotate">Rotation</option><option value="level" disabled={tag?.data_type === 'BOOL'}>Niveau (0 à 100 %)</option><option value="position" disabled={tag?.data_type === 'BOOL'}>Position (0 à 100 %)</option></select></label>
      {['level', 'position'].includes(animation.effect) && <div className="animation-condition"><label>Valeur pour 0 %<input aria-label="Animation minimum" type="number" step="any" disabled={locked} value={animation.min} onChange={event => patch({ min: Number(event.target.value) })} /></label><label>Valeur pour 100 %<input aria-label="Animation maximum" type="number" step="any" disabled={locked} value={animation.max} onChange={event => patch({ max: Number(event.target.value) })} /></label></div>}
      <div className="animation-colors"><label>Couleur active<input type="color" aria-label="Couleur active" disabled={locked} value={animation.active_color ?? '#079c83'} onChange={event => patch({ active_color: event.target.value })} /></label><label>Couleur inactive<input type="color" aria-label="Couleur inactive" disabled={locked} value={animation.inactive_color ?? '#6d8291'} onChange={event => patch({ inactive_color: event.target.value })} /></label></div>
      <p className={`animation-live ${reading?.available ? '' : 'unavailable'}`}>{reading?.available ? `Lu ${fmt(state?.tags[animation.tag_id]?.value)} · ${reading.active ? 'Condition active' : 'Condition inactive'}` : reading?.initial ? 'Valeur initiale · aucun échange acquis' : `Valeur indisponible · ${state?.tags[animation.tag_id]?.quality ?? 'non acquise'}`}</p>
    </>}
  </section>;
}
