import { useEffect, useRef, useState } from 'react';
import { Check, ChevronRight, CircleAlert, Crosshair, LoaderCircle, Play } from 'lucide-react';
import { api } from './api';
import { actionPreview, engineeringUnit, OPERATORS, tagReference } from './signal';
import { fmt, type PreparedCheck, type Project, type Scalar, type Scenario, type Snapshot } from './types';

function checkNow(check: PreparedCheck, live: Snapshot['tags'][string] | undefined): boolean | null {
  if (!live || !['good', 'forced', 'out_of_range', 'fault'].includes(live.quality)) return null;
  const actual = live.value;
  const expected = check.value;
  const equal = typeof actual === 'boolean' ? actual === expected : typeof expected === 'number' && Math.abs(actual - expected) <= check.tolerance;
  if (check.operator === 'eq') return equal;
  if (check.operator === 'ne') return !equal;
  if (typeof actual !== 'number' || typeof expected !== 'number') return false;
  return check.operator === 'gt' ? actual > expected : check.operator === 'ge' ? actual >= expected : check.operator === 'lt' ? actual < expected : actual <= expected;
}

type Props = { project: Project; scenario: Scenario; state: Snapshot | null; online: boolean; onSnapshot: (state: Snapshot) => void; onError: (message: string) => void; onPrepare: () => void; observations: Record<string, string>; onObservationChange: (key: string, text: string) => void };

export function GuidedRun({ project, scenario, state, online, onSnapshot, onError, onPrepare, observations, onObservationChange }: Props) {
  const steps = scenario.fat_steps ?? [];
  const active = state?.scenario.id === scenario.id;
  const results = active ? state.guided_steps ?? [] : [];
  const reviewed = results.filter(result => result.state === 'reviewed');
  const currentIndex = Math.min(reviewed.length, Math.max(0, steps.length - 1));
  const [selectedId, setSelectedId] = useState(steps[currentIndex]?.id ?? '');
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const currentStepId = steps[currentIndex]?.id;
  useEffect(() => { setSelectedId(currentStepId ?? ''); }, [scenario.id, state?.run_id, currentStepId]);
  const selected = steps.find(step => step.id === selectedId) ?? steps[currentIndex];
  const selectedIndex = selected ? steps.findIndex(step => step.id === selected.id) : -1;
  const result = results.find(result => result.id === selected?.id);
  const observationKey = `${state?.run_id ?? 'preparation'}:${selected?.id ?? ''}`;
  const observation = observations[observationKey] ?? result?.observation ?? '';
  const setObservation = (text: string) => onObservationChange(observationKey, text);
  const finished = active && state.scenario.state === 'completed';
  const canCommand = Boolean(online && active && state?.status === 'running' && !finished && selectedIndex === reviewed.length && !busy);
  const canExecute = canCommand && !result;
  const canObserve = canCommand && result?.state === 'applied';
  const failingNow = selected?.checks.some(check => checkNow(check, state?.tags[check.target]) !== true) ?? false;
  const mutate = async (operation: 'execute' | 'observe', verdict?: 'pass' | 'fail') => {
    if (busyRef.current || !selected || !state?.run_id || operation === 'execute' && !canExecute || operation === 'observe' && !canObserve) return;
    busyRef.current = true; setBusy(true);
    try {
      onSnapshot(await api<Snapshot>(`/run/steps/${encodeURIComponent(selected.id)}/${operation}`, 'POST', operation === 'observe' ? { verdict, observation } : {}, undefined, state.run_id));
    } catch (error) { onError(error instanceof Error ? error.message : String(error)); }
    finally { busyRef.current = false; setBusy(false); }
  };

  return <section className={`fat-run guided-run ${reviewed.some(result => result.verdict === 'fail') ? 'has-failure' : ''}`} aria-label="Suivi de la FAT pas à pas">
    <div className="fat-run-heading"><div><span className="fat-requirement">{scenario.requirement || 'FAT pas à pas'}</span><h3>{scenario.name}</h3><p>{scenario.description}</p></div><div className="fat-run-metrics"><strong>{reviewed.length} / {steps.length} étapes observées</strong><span>{active ? `${fmt(state.sim_time_s)} s · temps simulé` : 'Prêt à démarrer'}</span><button className="button compact-button" onClick={onPrepare}><Crosshair size={14} />Préparer la vue</button></div></div>
    <div className="fat-progress" role="progressbar" aria-label="Progression des observations" aria-valuemin={0} aria-valuemax={steps.length} aria-valuenow={reviewed.length}><span style={{ width: `${steps.length ? reviewed.length / steps.length * 100 : 0}%` }} /></div>
    {scenario.preconditions && <p className="fat-preconditions"><strong>Conditions initiales</strong> {scenario.preconditions}</p>}
    <ol className="grafcet-strip execution-strip" aria-label="Étapes de la FAT">{steps.map((step, index) => {
      const recorded = results.find(result => result.id === step.id);
      const next = index === reviewed.length && !finished;
      return <li key={step.id} className={`${selected?.id === step.id ? 'selected' : ''} ${recorded?.verdict === 'pass' ? 'passed' : recorded?.verdict === 'fail' ? 'failed' : ''} ${next ? 'current' : ''}`}><button aria-label={`Voir STEP ${index + 1} : ${step.name}`} aria-current={selected?.id === step.id ? 'step' : undefined} onClick={() => setSelectedId(step.id)}><span className="grafcet-number">{recorded?.state === 'reviewed' ? recorded.verdict === 'pass' ? <Check size={17} /> : <CircleAlert size={17} /> : index + 1}</span><span><small>STEP {index + 1} · {recorded?.state === 'reviewed' ? recorded.verdict === 'pass' ? 'Conforme' : 'Écart' : recorded?.state === 'queued' ? 'Application en cours' : recorded?.state === 'applied' ? 'À observer' : next ? 'À exécuter' : 'À venir'}</small><strong>{step.name}</strong></span></button>{index < steps.length - 1 && <ChevronRight size={16} className="grafcet-link" />}</li>;
    })}</ol>
    {selected && <div className="guided-current-step" key={`${state?.run_id}-${selected.id}`}>
      <div className="guided-step-title"><span className="step-badge">STEP {selectedIndex + 1}</span><h4>{selected.name}</h4>{result?.applied_s != null && <small>Appliqué à {fmt(result.applied_s)} s</small>}</div>
      <div className="guided-instructions"><div><span className="field-caption">Instructions</span><p>{selected.instructions || 'Appliquer les écritures préparées et observer le procédé.'}</p></div><div className="guided-expected"><span className="field-caption">Résultat attendu</span><p>{selected.expected_result || 'Voir les contrôles mesurables ci-dessous.'}</p></div></div>
      {selected.actions.length > 0 && <div className="table-container prepared-run-actions"><table><thead><tr><th>Entrée PLC</th><th>Action préparée</th><th>Valeur native</th><th>Valeur actuelle</th></tr></thead><tbody>{selected.actions.map((action, index) => {
        const tag = project.tags.find(tag => tag.id === action.target);
        const applied = result?.actions[index];
        return <tr key={index}><td><strong>{tag?.name ?? action.target}</strong><small className="table-reference">{tag ? tagReference(tag) : ''}</small></td><td>{action.action === 'release' ? 'Libérer' : `Écrire ${fmt(action.value, 3)} ${action.unit === 'native' ? tag?.unit ?? '' : action.unit === 'percent' ? '%' : action.unit === 'engineering' && tag ? engineeringUnit(tag) : action.unit}`}{action.diagnostic && <small className="table-reference">Diagnostic hors plage · profil déclaré</small>}</td><td><code>{applied ? action.action === 'release' ? 'Libéré' : `${fmt(applied.raw_value, 5)} ${tag?.unit ?? ''}` : actionPreview(tag, action)}</code></td><td className="mono">{fmt(state?.tags[action.target]?.value, 3)}<small className="table-reference">{state?.tags[action.target]?.quality ?? 'Non acquis'}</small></td></tr>;
      })}</tbody></table></div>}
      {selected.checks.length > 0 && <div className="guided-check-table table-container"><table><thead><tr><th>Contrôle mesurable</th><th>Attendu</th><th>Réel</th><th>{result?.state === 'reviewed' ? 'Contrôle enregistré' : 'Mesure en direct'}</th></tr></thead><tbody>{selected.checks.map((check, index) => {
        const tag = project.tags.find(tag => tag.id === check.target);
        const saved = result?.checks.find(item => item.index === index);
        const live = state?.tags[check.target];
        const measured = saved ? saved.passed : active && result?.state === 'applied' ? checkNow(check, live) : null;
        const actual: Scalar | undefined = saved?.actual ?? (active ? live?.value : undefined);
        return <tr key={index} className={measured === false ? 'measured-fail' : measured === true ? 'measured-pass' : ''}><td><strong>{tag?.name ?? check.target}</strong><small className="table-reference">{tag ? tagReference(tag) : ''}</small></td><td>{OPERATORS[check.operator]} {fmt(check.value, 5)} {tag?.unit}{typeof check.value === 'number' && ['eq', 'ne'].includes(check.operator) && <small className="table-reference">Tolérance ±{fmt(check.tolerance, 5)}</small>}</td><td className="mono">{fmt(actual, 5)} {tag?.unit}<small className="table-reference">{saved?.quality ?? (active ? live?.quality : null) ?? 'Non acquis'}</small></td><td>{measured == null ? 'À contrôler' : measured ? 'Valeur attendue' : 'Écart mesuré'}{saved && <small className="table-reference">À {fmt(saved.evaluated_s)} s</small>}</td></tr>;
      })}</tbody></table></div>}
      {result?.state === 'reviewed' ? <div className={`step-observation recorded ${result.verdict}`}><strong>Observation enregistrée · {result.verdict === 'pass' ? 'Conforme' : 'Écart'} à {fmt(result.observed_s)} s</strong><p>{result.observation || 'Aucune note complémentaire.'}</p></div> : <div className="step-execution-controls">
        {!result && <><button className="button primary execute-fat-step" disabled={!canExecute} onClick={() => void mutate('execute')}><Play size={15} fill="currentColor" />Exécuter STEP {selectedIndex + 1}</button><span className="small-muted">{!active ? 'Sélectionnez cette FAT et démarrez l’essai.' : state?.status === 'paused' ? 'Reprenez l’essai pour poursuivre.' : selectedIndex > reviewed.length ? 'Consignez le résultat de l’étape précédente pour déverrouiller celle-ci.' : 'Applique les écritures préparées de cette étape.'}</span></>}
        {result?.state === 'queued' && <p className="step-queued" role="status"><LoaderCircle size={17} className="spin" />Écritures en cours d’application. Attendez la confirmation du cycle.</p>}
        {result?.state === 'applied' && <div className="step-observation"><label>Observation du testeur<textarea disabled={!canObserve} rows={3} maxLength={4000} value={observation} placeholder="Comportement constaté, mesure, réserve ou écart…" onChange={event => setObservation(event.target.value)} /></label><div className="human-step-decision"><span>Votre résultat pour STEP {selectedIndex + 1}</span><div className="button-row"><button className="button pass-button" disabled={!canObserve || failingNow} onClick={() => void mutate('observe', 'pass')}><Check size={16} />Conforme</button><button className="button fail-button" disabled={!canObserve} onClick={() => void mutate('observe', 'fail')}><CircleAlert size={16} />Écart</button></div></div>{failingNow && <p className="step-missing-expectation"><CircleAlert size={14} />Un contrôle mesuré est en écart ou sans qualité valide. Corrigez la mesure ou consignez « Écart ».</p>}<p className="small-muted">Votre choix enregistre l’observation et déverrouille le STEP suivant.</p></div>}
      </div>}
    </div>}
    {finished && <div className="fat-human-result">Toutes les étapes ont été observées. Conclusion FAT humaine : {state.result.verdict === 'not_evaluated' ? 'à renseigner dans le rapport' : state.result.verdict === 'pass' ? 'conforme' : 'non conforme'}.</div>}
  </section>;
}
