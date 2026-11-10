import { useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { isFlowEquipment } from './processCircuits';
import { useModalKeyboard } from './useModalKeyboard';
import { fmt, type CatalogItem, type Project, type Snapshot } from './types';
import './flow-library.css';

type FlowFact = {
  calculated_at_s: number; step_s: number; command: boolean | number; target_pct: number; actual_pct: number;
  max_flow_l_s: number; available_flow_l_s: number; requested_flow_l_s: number; actual_flow_l_s: number;
  circuit_equipment_ids: string[]; limiting_equipment_ids: string[]; source_tank_id: string;
  source_factor: number; source_volume_l: number | null; external_supply_l: number | null; reasons: string[];
};
function fact(state: Snapshot | null, id: string): FlowFact | null {
  const value = state?.equipment[id]?.flow_diagnostic as FlowFact | undefined;
  return value && Number.isFinite(value.calculated_at_s) && Number.isFinite(value.actual_flow_l_s) && Array.isArray(value.circuit_equipment_ids) ? value : null;
}
const reasons: Record<string, string> = {
  command_off: 'Commande d’arrêt ou de fermeture reçue.', motor_trip: 'Défaut moteur actif : débit moteur coupé.',
  speed_setpoint: 'La consigne de vitesse est inférieure à 100 %.', valve_stuck: 'La position est imposée par un défaut de vanne bloquée.',
  valve_closed: 'La vanne est fermée.', partial_open: 'La vanne est partiellement ouverte.',
  response_pending: 'Le temps de réponse du modèle retarde la position ou la vitesse demandée.',
};
type Props = { project: Project; state: Snapshot | null; catalog: CatalogItem[]; equipmentId?: string; modelDirty?: boolean;
  unavailable?: string; onFocus: (id: string) => void; onClose: () => void };

export function FlowExplanation({ project, state, catalog, equipmentId, modelDirty, unavailable, onFocus, onClose }: Props) {
  const actuators = project.equipment.filter(isFlowEquipment);
  const [selected, setSelected] = useState(actuators.some(item => item.id === equipmentId) ? equipmentId! : actuators[0]?.id ?? '');
  const device = actuators.find(item => item.id === selected);
  const current = fact(state, selected);
  const ids = current?.circuit_equipment_ids ?? (device ? [device.id] : []);
  const devices = actuators.filter(item => ids.includes(item.id));
  const badCommand = state?.status === 'running' && devices.some(item => ['command', 'speed_command'].some(port => {
    const id = item.bindings[port]; return id && !['good', 'forced'].includes(state.tags[id]?.quality ?? 'unknown');
  }));
  const blocked = unavailable || (modelDirty ? 'Le brouillon a changé. Enregistrez le modèle avant de relire ses débits.'
    : state?.status === 'error' ? 'Le service a signalé une erreur. Les anciennes valeurs ne permettent pas d’expliquer le débit actuel.'
    : !state || state.status === 'idle' ? 'Démarrez un essai pour calculer les débits du modèle.'
    : badCommand || (state.status === 'running' && state.connection.quality !== 'good') ? 'Qualité des échanges indisponible. Aucun diagnostic de débit actuel.'
    : !current ? 'Un nouveau cycle est nécessaire après la modification du modèle ou d’un défaut.' : '');
  useModalKeyboard(true, onClose);
  const name = (id: string) => project.equipment.find(item => item.id === id)?.name ?? id;
  return createPortal(<div className="modal-backdrop"><section className="modal flow-modal" role="dialog" aria-modal="true" aria-labelledby="flow-explanation-title">
    <div className="modal-heading"><h2 id="flow-explanation-title">Comprendre le débit</h2><button className="icon-button" aria-label="Fermer l’explication des débits" onClick={onClose}><X size={18} /></button></div>
    <label>Pompe ou vanne à examiner<select aria-label="Équipement du débit" value={selected} onChange={event => setSelected(event.target.value)}>{actuators.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    {!actuators.length ? <p>Ajoutez un circuit avec une pompe ou une vanne pour examiner son débit.</p> : blocked ? <p className="binding-notice" role="status">{blocked}</p> : current && <>
      <p className="flow-timestamp" role="status">{state?.status === 'paused' ? 'Essai en pause : dernier cycle calculé' : state?.status === 'stopped' ? 'Essai arrêté : dernier cycle calculé, valeurs historiques' : 'Dernier cycle calculé'} à {fmt(current.calculated_at_s)} s. Pas de calcul : {fmt(current.step_s)} s.</p>
      <div className="flow-summary"><strong>Débit calculé : {fmt(current.actual_flow_l_s)} L/s</strong><span>Capacité du circuit en série : {fmt(current.requested_flow_l_s)} L/s</span></div>
      {current.source_factor < 1 && <div className="binding-notice"><strong>{current.source_factor === 0 ? 'La source ne dispose pas de liquide pour ce cycle.' : 'Le volume disponible dans la source limite le débit.'}</strong><p><button className="flow-link" onClick={() => onFocus(current.source_tank_id)}>{name(current.source_tank_id)}</button> : {fmt(current.source_volume_l ?? 0)} L au début du cycle, plus {fmt(current.external_supply_l ?? 0)} L d’alimentation extérieure. Les autres sorties de cette cuve partagent ce volume.</p></div>}
      <p>La capacité en série est limitée par {current.limiting_equipment_ids.map((id, index) => <span key={id}>{index > 0 ? ', ' : ''}<button className="flow-link" onClick={() => onFocus(id)}>{name(id)}</button></span>)}. Les circuits indépendants s’additionnent.</p>
      <div className="flow-device-list">{devices.map(item => {
        const itemFact = fact(state, item.id);
        if (!itemFact) return null;
        const isPump = item.type === 'pump' || item.type === 'pump_vfd';
        return <article key={item.id} className={current.limiting_equipment_ids.includes(item.id) ? 'limiting' : ''}>
          <div><button className="flow-link" onClick={() => onFocus(item.id)}>{item.name}</button><span>{catalog.find(spec => spec.type === item.type)?.label}</span>{current.limiting_equipment_ids.includes(item.id) && <small>Organe limitant</small>}</div>
          <dl><div><dt>Commande reçue</dt><dd>{typeof itemFact.command === 'boolean' ? itemFact.command ? 'TRUE' : 'FALSE' : `${fmt(itemFact.command)} %`}</dd></div><div><dt>{isPump ? 'Vitesse calculée / demandée' : 'Position calculée / demandée'}</dt><dd>{fmt(itemFact.actual_pct)} / {fmt(itemFact.target_pct)} %</dd></div><div><dt>Capacité disponible / maximale</dt><dd>{fmt(itemFact.available_flow_l_s)} / {fmt(itemFact.max_flow_l_s)} L/s</dd></div></dl>
          <ul>{itemFact.reasons.length ? itemFact.reasons.map(reason => <li key={reason}>{reasons[reason] ?? reason}</li>) : <li>Capacité maximale disponible pour cet organe.</li>}</ul>
        </article>;
      })}</div>
    </>}
    <p className="small-muted">Ces faits décrivent le modèle de procédé et les commandes reçues. Les interverrouillages internes du programme automate ne sont pas déduits. Une conduite dessinée seule ne crée pas un transfert physique.</p>
    <div className="modal-actions"><button className="button" onClick={onClose}>Fermer</button></div>
  </section></div>, document.body);
}
