import { ArrowRight, FolderOpen, Play, Workflow, X } from 'lucide-react';
import type { Project, Snapshot } from './types';

export function Welcome({ project, disabled, onDemo, onCreate, onResume, onOpen }: { project: Project; disabled: boolean; onDemo: () => void; onCreate: () => void; onResume: () => void; onOpen: () => void }) {
  return <section className="welcome" aria-label="Bienvenue dans Vanguard FAT Studio"><div className="welcome-heading"><div><span className="eyebrow">VANGUARD FAT STUDIO</span><h1>Votre premier essai commence ici.</h1><p>Construisez un procédé, reliez ses variables et observez son fonctionnement.</p></div><button className="icon-button" aria-label="Fermer l’accueil" onClick={onResume}><X size={20} /></button></div><div className="welcome-actions">
    <button className="welcome-card welcome-demo" aria-label="Essayer la démo" disabled={disabled} onClick={onDemo}><Play size={24} /><strong>Essayer la démo</strong><span>Une cuve, une pompe et une vanne. Sans automate ni TIA Portal.</span><ArrowRight size={18} /></button>
    <button className="welcome-card" aria-label="Créer mon procédé" disabled={disabled} onClick={onCreate}><Workflow size={24} /><strong>Créer mon procédé</strong><span>Partez d’un circuit ou assemblez vos équipements.</span><ArrowRight size={18} /></button>
    <button className="welcome-card" aria-label="Reprendre mon projet" onClick={onResume}><FolderOpen size={24} /><strong>Reprendre mon projet</strong><span>{project.name}</span><ArrowRight size={18} /></button>
  </div><div className="welcome-footer"><span>Gratuit et open source · fichiers conservés sur ce poste</span><button className="text-link" disabled={disabled} onClick={onOpen}>Ouvrir un autre projet ou le laboratoire</button></div></section>;
}

export function FirstRunGuide({ project, state, disabled, onCommand, onFault, onDismiss }: { project: Project; state: Snapshot | null; disabled: boolean; onCommand: (id: string, value: boolean) => void; onFault: (id: string, active: boolean) => void; onDismiss: () => void }) {
  const pump = project.equipment.find(item => item.type === 'pump');
  const valve = project.equipment.find(item => item.type === 'valve_onoff');
  const tank = project.equipment.find(item => item.type === 'tank');
  const running = state?.status === 'running';
  const request = (id?: string) => Boolean(id && state?.tags[id]?.value);
  const fault = Boolean(pump && state?.faults[pump.id]?.motor_trip);
  return <section className="first-run-guide" role="region" aria-label="Votre premier essai"><div><strong>Votre premier essai</strong><p>{!running ? 'Cliquez sur Démarrer, puis commandez la pompe et la vanne ci-dessous.' : 'Observez le niveau de la cuve. Essayez ensuite un défaut moteur et son rétablissement.'}</p></div><div className="button-row">
    {pump?.bindings.manual_request && <button className="button" disabled={disabled || !running} aria-pressed={request(pump.bindings.manual_request)} onClick={() => onCommand(pump.bindings.manual_request, !request(pump.bindings.manual_request))}>{request(pump.bindings.manual_request) ? 'Arrêter la pompe' : 'Mettre la pompe en marche'}</button>}
    {valve?.bindings.manual_request && <button className="button" disabled={disabled || !running} aria-pressed={request(valve.bindings.manual_request)} onClick={() => onCommand(valve.bindings.manual_request, !request(valve.bindings.manual_request))}>{request(valve.bindings.manual_request) ? 'Fermer la vanne' : 'Ouvrir la vanne'}</button>}
    {pump && <button className="button" disabled={disabled || !running} aria-pressed={fault} onClick={() => onFault(pump.id, !fault)}>{fault ? 'Rétablir le moteur' : 'Essayer un défaut moteur'}</button>}
    {tank && <span className="first-run-level">Niveau : {Number(state?.equipment[tank.id]?.level ?? tank.params.initial_level_pct ?? 0).toLocaleString('fr-CH', { maximumFractionDigits: 1 })} %</span>}
  </div><button className="icon-button" aria-label="Masquer les indications" onClick={onDismiss}><X size={16} /></button></section>;
}
