import { Check, Circle, CircleAlert, Clock3, Crosshair, ListChecks, Play } from 'lucide-react';
import { fmt, type Project, type Scenario, type ScenarioStep, type Snapshot } from './types';
import { GuidedRun } from './GuidedRun';

const OPERATORS: Record<string, string> = { eq: '=', ne: '≠', gt: '>', ge: '≥', lt: '<', le: '≤' };
const ACTIONS: Record<ScenarioStep['action'], string> = { force: 'Écrire', release: 'Libérer', fault: 'Injecter le défaut', clear_fault: 'Retirer le défaut', marker: 'Observation', expect: 'Vérifier' };

export function stepText(project: Project, step: ScenarioStep): string {
  const tag = project.tags.find(tag => tag.id === step.target);
  const equipment = project.equipment.find(item => item.id === step.target);
  const target = tag?.name ?? equipment?.name ?? step.target ?? '';
  if (step.action === 'expect') return `${target} ${OPERATORS[step.operator ?? 'eq']} ${fmt(step.value)}${tag?.unit ? ' ' + tag.unit : ''}${step.operator === 'eq' && tag?.data_type !== 'BOOL' ? ` (±${fmt(step.tolerance ?? .001, 3)})` : ''}`;
  if (step.action === 'force') return `${target} ← ${fmt(step.value)}${tag?.unit ? ' ' + tag.unit : ''}`;
  if (step.action === 'fault') {
    const kind = typeof step.value === 'object' && step.value ? (step.value as { kind?: string }).kind : '';
    const labels: Record<string, string> = { motor_trip: 'défaut moteur', valve_stuck: 'vanne bloquée', out_of_range: 'signal hors plage', sensor_stuck: 'capteur figé' };
    return `${target} · ${labels[kind ?? ''] ?? kind ?? ''}`;
  }
  return step.action === 'marker' ? step.message || String(step.value ?? '') : target;
}

export function scenarioFocus(project: Project, scenario: Scenario): string[] {
  const targets = new Set(scenario.execution_mode === 'guided' ? (scenario.fat_steps ?? []).flatMap(step => [...step.actions, ...step.checks].map(item => item.target)) : scenario.steps.map(step => step.target));
  return scenario.focus_equipment?.length ? scenario.focus_equipment : project.equipment.filter(item => targets.has(item.id) || Object.values(item.bindings).some(id => targets.has(id))).map(item => item.id);
}

export function ScenarioTimeline({ project, scenario, state, compact = false }: { project: Project; scenario: Scenario; state: Snapshot | null; compact?: boolean }) {
  const active = state?.scenario.id === scenario.id;
  const completed = new Set(active ? state.scenario.completed_step_indices ?? [] : []);
  const results = new Map(active ? state.scenario.assertions.map(assertion => [assertion.index, assertion]) : []);
  const next = scenario.steps.findIndex((_, index) => !completed.has(index) && !results.has(index));
  return <ol className={`fat-timeline ${compact ? 'compact' : ''}`} aria-label="Déroulé de la FAT">{scenario.steps.map((step, index) => {
    const result = results.get(index);
    const done = completed.has(index) || Boolean(result);
    const status = result ? result.passed ? 'passed' : 'failed' : done ? 'done' : active && index === next && state.status === 'running' ? 'current' : 'pending';
    return <li key={index} className={status} data-step={index}>
      <span className="fat-step-icon">{status === 'failed' ? <CircleAlert size={15} /> : done ? <Check size={15} /> : status === 'current' ? <Play size={12} fill="currentColor" /> : <Circle size={12} />}</span>
      <time>{fmt(step.at_s)} s</time><div><span className="fat-step-action">{ACTIONS[step.action]}</span><strong>{stepText(project, step)}</strong>{step.message && step.action !== 'marker' && <small>{step.message}</small>}</div>
      <span className={`step-result ${status}`}>{result ? <><b>{result.passed ? 'Conforme' : 'Écart'}</b><small>Lu : {fmt(result.actual)} · {result.quality}</small></> : done ? 'Exécuté' : active && ['error', 'stopped'].includes(state.status) ? 'Non exécuté' : 'À venir'}</span>
    </li>;
  })}</ol>;
}

export function ScenarioRun({ project, state, scenario, onPrepare, online, onSnapshot, onError, observations, onObservationChange }: { project: Project; state: Snapshot | null; scenario: Scenario | null; onPrepare: () => void; online: boolean; onSnapshot: (state: Snapshot) => void; onError: (message: string) => void; observations: Record<string, string>; onObservationChange: (key: string, text: string) => void }) {
  if (!scenario) return <div className="fat-run-free"><ListChecks size={17} /><span><strong>Essai libre</strong> · Sélectionnez une FAT pour préparer la vue et suivre ses contrôles.</span></div>;
  if (scenario.execution_mode === 'guided') return <GuidedRun project={project} state={state} scenario={scenario} onPrepare={onPrepare} online={online} onSnapshot={onSnapshot} onError={onError} observations={observations} onObservationChange={onObservationChange} />;
  const active = state?.scenario.id === scenario.id;
  const results = active ? state.scenario.assertions : [];
  const checks = scenario.steps.filter(step => step.action === 'expect').length;
  const passed = results.filter(result => result.passed).length;
  const failed = results.length - passed;
  const progress = active ? Math.min(100, state.sim_time_s / scenario.duration_s * 100) : 0;
  const finished = active && state.scenario.state === 'completed';
  return <section className={`fat-run ${failed ? 'has-failure' : ''}`} aria-label="Suivi de la FAT">
    <div className="fat-run-heading"><div><span className="fat-requirement">{scenario.requirement || 'Plan de test'}</span><h3>{scenario.name}</h3><p>{scenario.description}</p></div>
      <div className="fat-run-metrics"><span><Clock3 size={13} />{fmt(active ? state.sim_time_s : 0)} / {fmt(scenario.duration_s)} s</span><strong>{passed} / {checks} contrôles conformes</strong>{failed > 0 && <b className="failed-text">{failed} écart{failed > 1 ? 's' : ''}</b>}<button className="button compact-button" onClick={onPrepare}><Crosshair size={14} />Préparer la vue</button></div>
    </div>
    <div className="fat-progress" role="progressbar" aria-label="Progression du scénario" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><span style={{ width: `${progress}%` }} /></div>
    {scenario.preconditions && <p className="fat-preconditions"><strong>Conditions initiales</strong> {scenario.preconditions}</p>}
    <details className="fat-run-details" open><summary>{finished ? 'FAT terminée' : active ? 'Déroulé en cours' : 'Déroulé prévu'}<span>{scenario.steps.length} étapes · {checks} contrôles attendus</span></summary><ScenarioTimeline project={project} scenario={scenario} state={state} compact /></details>
    {finished && <div className="fat-human-result">Contrôles automatiques terminés. Conclusion FAT humaine : {state.result.verdict === 'not_evaluated' ? 'à renseigner dans le rapport' : state.result.verdict}.</div>}
  </section>;
}
