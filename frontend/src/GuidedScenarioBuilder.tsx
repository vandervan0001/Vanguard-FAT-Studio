import { useEffect, useState } from 'react';
import { ArrowDown, ArrowUp, ChevronRight, CircleAlert, ListChecks, Plus, Trash2 } from 'lucide-react';
import { actionPreview, displayValue, nativeValue, OPERATORS, stimulusUnits, tagOption, tagReference } from './signal';
import { fmt, uid, type FatStep, type PreparedAction, type PreparedCheck, type Project, type Scenario, type Tag } from './types';

export function newFatStep(): FatStep {
  return { id: uid('step'), name: 'Nouvelle étape', instructions: '', expected_result: '', actions: [], checks: [] };
}

function valueForTag(tag: Tag): PreparedAction {
  const unit = tag.signal ? 'engineering' : 'native';
  return { action: 'force', target: tag.id, value: displayValue(tag, tag.initial_value, unit), unit, diagnostic: false };
}

export function GuidedScenarioBuilder({ project, scenario, locked, onChange }: { project: Project; scenario: Scenario; locked: boolean; onChange: (patch: Partial<Scenario>) => void }) {
  const steps = scenario.fat_steps ?? [];
  const [selectedId, setSelectedId] = useState(steps[0]?.id ?? '');
  useEffect(() => { if (!steps.some(step => step.id === selectedId)) setSelectedId(steps[0]?.id ?? ''); }, [steps, selectedId]);
  const selected = steps.find(step => step.id === selectedId);
  const selectedIndex = steps.findIndex(step => step.id === selectedId);
  const writable = project.tags.filter(tag => tag.direction === 'input' && tag.writable);
  const update = (patch: Partial<FatStep>) => onChange({ fat_steps: steps.map(step => step.id === selectedId ? { ...step, ...patch } : step) });
  const addStep = () => { const step = { ...newFatStep(), name: `Étape ${steps.length + 1}` }; onChange({ fat_steps: [...steps, step] }); setSelectedId(step.id); };
  const move = (direction: number) => {
    const next = [...steps];
    [next[selectedIndex], next[selectedIndex + direction]] = [next[selectedIndex + direction], next[selectedIndex]];
    onChange({ fat_steps: next });
  };
  const actionChange = (index: number, patch: Partial<PreparedAction>) => { if (selected) update({ actions: selected.actions.map((action, current) => current === index ? { ...action, ...patch } : action) }); };
  const checkChange = (index: number, patch: Partial<PreparedCheck>) => { if (selected) update({ checks: selected.checks.map((check, current) => current === index ? { ...check, ...patch } : check) }); };

  return <section className="guided-builder" aria-label="Constructeur FAT pas à pas">
    <div className="guided-builder-heading"><div><ListChecks size={17} /><h3>FAT pas à pas</h3></div><p>Préparez chaque STEP, appliquez ses entrées pendant l’essai, puis consignez le résultat avant de poursuivre.</p></div>
    <ol className="grafcet-strip" aria-label="Ordre des étapes">{steps.map((step, index) => <li key={step.id} className={step.id === selectedId ? 'selected' : ''}><button aria-label={`Préparer STEP ${index + 1} : ${step.name}`} aria-current={step.id === selectedId ? 'step' : undefined} onClick={() => setSelectedId(step.id)}><span className="grafcet-number">{index + 1}</span><span><small>STEP {index + 1}</small><strong>{step.name}</strong></span></button>{index < steps.length - 1 && <ChevronRight size={16} className="grafcet-link" />}</li>)}</ol>
    <button className="button compact-button add-fat-step" disabled={locked || steps.length >= 100} onClick={addStep}><Plus size={15} />Ajouter une étape</button>
    {!selected ? <p className="small-muted">Ajoutez la première étape pour préparer la FAT.</p> : <div className="fat-step-editor" key={selected.id} data-step-id={selected.id}>
      <div className="fat-step-editor-heading"><span className="step-badge">STEP {selectedIndex + 1}</span><label>Nom de l’étape<input maxLength={200} disabled={locked} value={selected.name} onChange={event => update({ name: event.target.value })} /></label><div className="button-row"><button className="icon-button" disabled={locked || selectedIndex === 0} aria-label="Monter l’étape" title="Monter l’étape" onClick={() => move(-1)}><ArrowUp size={16} /></button><button className="icon-button" disabled={locked || selectedIndex === steps.length - 1} aria-label="Descendre l’étape" title="Descendre l’étape" onClick={() => move(1)}><ArrowDown size={16} /></button><button className="icon-button danger-text" disabled={locked} aria-label="Supprimer l’étape" title="Supprimer l’étape" onClick={() => { if (window.confirm(`Supprimer STEP ${selectedIndex + 1} « ${selected.name} » ?`)) onChange({ fat_steps: steps.filter(step => step.id !== selected.id) }); }}><Trash2 size={16} /></button></div></div>
      <label>Instructions du testeur<textarea disabled={locked} rows={3} maxLength={4000} value={selected.instructions} placeholder="Préparation, manœuvres à effectuer et points à observer sur le P&ID ou dans TIA." onChange={event => update({ instructions: event.target.value })} /></label>
      <div className="prepared-section-title"><h4>Écritures préparées</h4><button className="button compact-button" disabled={locked || selected.actions.length >= 100 || !writable.some(tag => !selected.actions.some(action => action.target === tag.id))} onClick={() => { const tag = writable.find(tag => !selected.actions.some(action => action.target === tag.id)); if (tag) update({ actions: [...selected.actions, valueForTag(tag)] }); }}><Plus size={14} />Ajouter une écriture</button></div>
      <p className="small-muted">Toutes les écritures du STEP sont préparées ensemble. Seules les entrées simulées autorisées sont proposées.</p>
      {!selected.actions.length && <div className="prepared-empty">Aucune écriture. Cette étape peut servir à une manœuvre ou une observation manuelle.</div>}
      <div className="prepared-actions">{selected.actions.map((action, index) => {
        const tag = project.tags.find(tag => tag.id === action.target);
        return <div className="prepared-action" key={index} data-action={index}>
          <label className="prepared-target">Entrée PLC<select aria-label={`Entrée écriture ${index + 1}`} disabled={locked} value={action.target} onChange={event => { const tag = writable.find(tag => tag.id === event.target.value); if (tag) actionChange(index, { ...valueForTag(tag), action: action.action }); }}>
            {!writable.some(tag => tag.id === action.target) && <option value={action.target}>{action.target} · indisponible</option>}{writable.map(tag => <option disabled={selected.actions.some((entry, current) => current !== index && entry.target === tag.id)} key={tag.id} value={tag.id}>{tagOption(tag)}</option>)}
          </select><small className="target-reference">{tag ? tagReference(tag) : 'Variable inconnue'}</small></label>
          <label>Action<select aria-label={`Action écriture ${index + 1}`} disabled={locked} value={action.action} onChange={event => actionChange(index, { action: event.target.value as PreparedAction['action'] })}><option value="force">Écrire</option><option value="release">Libérer</option></select></label>
          <label>Valeur{tag?.data_type === 'BOOL' ? <select aria-label={`Valeur écriture ${index + 1}`} disabled={locked || action.action === 'release'} value={String(action.value)} onChange={event => actionChange(index, { value: event.target.value === 'true' })}><option value="false">FALSE · 0</option><option value="true">TRUE · 1</option></select> : <input aria-label={`Valeur écriture ${index + 1}`} disabled={locked || action.action === 'release'} type="number" step={action.unit === 'native' && tag?.data_type !== 'REAL' ? 1 : 'any'} value={typeof action.value === 'number' ? action.value : ''} onChange={event => actionChange(index, { value: Number(event.target.value) })} />}</label>
          <label>Unité<select aria-label={`Unité écriture ${index + 1}`} disabled={locked || action.action === 'release' || !tag?.signal} value={action.unit} onChange={event => { const unit = event.target.value as PreparedAction['unit']; if (tag) { let raw = tag.initial_value; try { raw = nativeValue(tag, action.value ?? tag.initial_value, action.unit, action.diagnostic); } catch { /* Fall back to the declared initial value for an invalid draft. */ } actionChange(index, { unit, value: displayValue(tag, raw, unit) }); } }}>{tag ? stimulusUnits(tag).map(([key, label]) => <option value={key} key={key}>{label}</option>) : <option value="native">Natif</option>}</select></label>
          <button className="icon-button danger-text" disabled={locked} aria-label={`Retirer écriture ${index + 1}`} onClick={() => update({ actions: selected.actions.filter((_, current) => current !== index) })}><Trash2 size={15} /></button>
          <div className="prepared-preview"><span>Aperçu PLC</span><code>{actionPreview(tag, action)}</code>{tag && tag.data_type !== 'BOOL' && <small>Limites natives : {fmt(tag.min)} à {fmt(tag.max)} {tag.unit}</small>}</div>
          {tag && tag.data_type !== 'BOOL' && <div className="prepared-diagnostic"><label className="check-label"><input aria-label={`Diagnostic écriture ${index + 1}`} type="checkbox" disabled={locked || action.action === 'release'} checked={action.diagnostic ?? false} onChange={event => actionChange(index, { diagnostic: event.target.checked })} />Stimulus de diagnostic hors plage</label>{tag.signal?.kind === '4-20mA' && action.diagnostic && <div className="button-row">{[0, 24].map(value => <button className="button compact-button" key={value} disabled={locked || action.action === 'release'} onClick={() => actionChange(index, { value, unit: 'mA' })}>Préparer {value} mA</button>)}<small>Codes du profil : {fmt(tag.signal.underflow_raw)} / {fmt(tag.signal.overflow_raw)}</small></div>}</div>}
        </div>;
      })}</div>
      <label className="expected-result-field">Résultat attendu<textarea disabled={locked} rows={3} maxLength={4000} value={selected.expected_result} placeholder="Décrivez la réaction attendue du PLC et le comportement à constater avant de valider cette étape." onChange={event => update({ expected_result: event.target.value })} /></label>
      {!selected.expected_result.trim() && !selected.checks.length && <p className="step-missing-expectation"><CircleAlert size={14} />Précisez le résultat attendu ou ajoutez un contrôle mesurable avant de démarrer.</p>}
      <div className="prepared-section-title"><h4>Contrôles mesurables (facultatifs)</h4><button className="button compact-button" disabled={locked || selected.checks.length >= 100 || !project.tags.length} onClick={() => { const tag = project.tags.find(tag => tag.direction === 'output') ?? project.tags[0]; if (tag) update({ checks: [...selected.checks, { target: tag.id, operator: 'eq', value: tag.initial_value, tolerance: tag.data_type === 'BOOL' ? 0 : .001 }] }); }}><Plus size={14} />Ajouter un contrôle</button></div>
      <p className="small-muted">Les valeurs sont contrôlées au moment où le testeur consigne son résultat. Le verdict de l’étape reste une décision humaine.</p>
      <div className="prepared-checks">{selected.checks.map((check, index) => {
        const tag = project.tags.find(tag => tag.id === check.target);
        return <div className="prepared-check" key={index} data-check={index}>
          <label>Variable à lire<select aria-label={`Variable contrôle ${index + 1}`} disabled={locked} value={check.target} onChange={event => { const tag = project.tags.find(tag => tag.id === event.target.value); if (tag) checkChange(index, { target: tag.id, value: tag.initial_value, operator: 'eq', tolerance: tag.data_type === 'BOOL' ? 0 : .001 }); }}>{!tag && <option value={check.target}>{check.target} · indisponible</option>}{project.tags.map(tag => <option key={tag.id} value={tag.id}>{tagOption(tag)}</option>)}</select></label>
          <label>Relation<select aria-label={`Relation contrôle ${index + 1}`} disabled={locked} value={check.operator} onChange={event => checkChange(index, { operator: event.target.value as PreparedCheck['operator'] })}>{Object.entries(OPERATORS).filter(([key]) => tag?.data_type !== 'BOOL' || ['eq', 'ne'].includes(key)).map(([key, symbol]) => <option key={key} value={key}>{symbol}</option>)}</select></label>
          <label>Attendu {tag?.unit}{tag?.data_type === 'BOOL' ? <select aria-label={`Attendu contrôle ${index + 1}`} disabled={locked} value={String(check.value)} onChange={event => checkChange(index, { value: event.target.value === 'true' })}><option value="false">FALSE</option><option value="true">TRUE</option></select> : <input aria-label={`Attendu contrôle ${index + 1}`} disabled={locked} type="number" step={tag?.data_type === 'REAL' ? 'any' : 1} value={Number(check.value)} onChange={event => checkChange(index, { value: Number(event.target.value) })} />}</label>
          <label>Tolérance ±<input aria-label={`Tolérance contrôle ${index + 1}`} disabled={locked || tag?.data_type === 'BOOL' || !['eq', 'ne'].includes(check.operator)} type="number" min={0} max={1e9} step="any" value={check.tolerance} onChange={event => checkChange(index, { tolerance: Number(event.target.value) })} /></label>
          <button className="icon-button danger-text" disabled={locked} aria-label={`Retirer contrôle ${index + 1}`} onClick={() => update({ checks: selected.checks.filter((_, current) => current !== index) })}><Trash2 size={15} /></button>
        </div>;
      })}</div>
    </div>}
  </section>;
}
