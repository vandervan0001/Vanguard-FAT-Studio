import { useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowDown, ArrowRight, ArrowUp, Copy, Plus, Route, X } from 'lucide-react';
import { CIRCUIT_TEMPLATES, circuitMembers, duplicateEquipment, insertCircuit, isFlowEquipment, planTransfer, type CircuitTemplate } from './processCircuits';
import { useModalKeyboard } from './useModalKeyboard';
import type { CatalogItem, Project } from './types';
import './process-builder.css';

type Mode = 'template' | 'transfer' | 'duplicate';
type Props = { project: Project; catalog: CatalogItem[]; locked: boolean; mode: Mode; equipmentId?: string;
  onApply: (base: Project, next: Project, selectedIds: string[]) => void; onClose: () => void };

export function TransferBuilder({ project, catalog, locked, mode: initialMode, equipmentId, onApply, onClose }: Props) {
  const [base] = useState(project);
  const [mode, setMode] = useState(initialMode);
  const [kind, setKind] = useState<CircuitTemplate>('transfer');
  const [withScenario, setWithScenario] = useState(false);
  const canCopyCircuit = base.equipment.some(item => item.id === equipmentId && isFlowEquipment(item));
  const [wholeCircuit, setWholeCircuit] = useState(canCopyCircuit);
  const tanks = base.equipment.filter(item => item.type === 'tank');
  const actuators = base.equipment.filter(isFlowEquipment);
  const initial = actuators.find(item => item.id === equipmentId) ?? actuators[0];
  const initialMembers = initial ? circuitMembers(base, catalog, initial.id).filter(isFlowEquipment) : [];
  const [sourceId, setSourceId] = useState(String(initial?.params.source_tank_id ?? ''));
  const [targetId, setTargetId] = useState(String(initial?.params.tank_id || tanks[0]?.id || ''));
  const [actuatorIds, setActuatorIds] = useState(initialMembers.map(item => item.id));
  const stale = project !== base;
  const disabled = locked || stale;
  useModalKeyboard(true, onClose);
  const preview = useMemo(() => {
    try {
      if (mode === 'template') {
        const result = insertCircuit(base, catalog, kind, withScenario);
        return { next: result.project, selectedIds: result.selectedIds, names: result.addedEquipment.map(item => item.name), tagCount: result.addedTags.length, removed: 0, error: '' };
      }
      if (mode === 'duplicate') {
        const result = duplicateEquipment(base, catalog, equipmentId ?? '', wholeCircuit);
        return { next: result.project, selectedIds: result.selectedIds, names: result.addedEquipment.map(item => item.name), tagCount: result.addedTags.length, removed: 0, error: '' };
      }
      const result = planTransfer(base, catalog, { sourceId, targetId, actuatorIds });
      return { next: result.project, selectedIds: result.selectedIds, names: [result.sourceName, ...result.actuatorNames, result.targetName], tagCount: 0, removed: result.removed.length, error: '' };
    } catch (error) { return { next: null, selectedIds: [], names: [], tagCount: 0, removed: 0, error: error instanceof Error ? error.message : String(error) }; }
  }, [base, catalog, kind, withScenario, mode, sourceId, targetId, actuatorIds, equipmentId, wholeCircuit]);
  const move = (index: number, direction: number) => setActuatorIds(current => {
    const next = [...current]; const to = index + direction;
    if (to >= 0 && to < next.length) [next[index], next[to]] = [next[to], next[index]];
    return next;
  });
  return createPortal(<div className="modal-backdrop"><section className="modal circuit-modal" role="dialog" aria-modal="true" aria-labelledby="circuit-builder-title">
    <div className="modal-heading"><div><div className="eyebrow">Construction du procédé</div><h2 id="circuit-builder-title">{mode === 'duplicate' ? 'Dupliquer dans le P&ID' : 'Circuits et transferts'}</h2></div><button className="icon-button" onClick={onClose} aria-label="Fermer le constructeur de circuit"><X size={18} /></button></div>
    {initialMode !== 'duplicate' && <div className="circuit-tabs" role="group" aria-label="Méthode de construction"><button className={mode === 'template' ? 'active' : ''} aria-pressed={mode === 'template'} onClick={() => setMode('template')}><Plus size={16} />Insérer un modèle</button><button className={mode === 'transfer' ? 'active' : ''} aria-pressed={mode === 'transfer'} onClick={() => setMode('transfer')}><Route size={16} />Relier mes équipements</button></div>}
    <div className="circuit-editor">
      <div>
        {mode === 'template' ? <>
          <p>Ajoutez un circuit avec ses conduites, paramètres physiques et tags locaux.</p>
          <div className="circuit-template-list" role="group" aria-label="Modèles de circuit">{CIRCUIT_TEMPLATES.map(item => <button key={item.id} aria-pressed={kind === item.id} className={kind === item.id ? 'active' : ''} onClick={() => setKind(item.id)}><strong>{item.name}</strong><span>{item.description}</span></button>)}</div>
          <label className="check-label circuit-scenario"><input type="checkbox" checked={withScenario} onChange={event => setWithScenario(event.target.checked)} />Ajouter une trame FAT à relire</label>
          {withScenario && <p className="small-muted">État initial, écoulement et arrêt : trois étapes d’observation à adapter. Aucune commande ni conclusion n’est préremplie.</p>}
        </> : mode === 'duplicate' ? <>
          <p>Copiez {base.equipment.find(item => item.id === equipmentId)?.name} avec de nouveaux repères et tags.</p>
          <label className="check-label"><input type="checkbox" checked={wholeCircuit} disabled={!canCopyCircuit} onChange={event => setWholeCircuit(event.target.checked)} />Inclure son circuit, les cuves et les capteurs associés</label>
          {!canCopyCircuit && <p className="small-muted">Pour copier un circuit complet, sélectionnez sa pompe ou sa vanne.</p>}
          <p className="small-muted">Les conduites et références à l’intérieur de la copie sont conservées. Les références à des équipements extérieurs à la copie restent à choisir.</p>
          <p className="small-muted">Les NodeIds, adresses et symboles PLC sont laissés vides. Les scénarios et historiques existants sont conservés sans être dupliqués.</p>
        </> : <>
          <p>Choisissez le trajet du liquide et l’ordre des pompes et vannes en série.</p>
          <div className="circuit-tanks"><label>Source du transfert<select aria-label="Source du transfert" value={sourceId} onChange={event => setSourceId(event.target.value)}><option value="">Alimentation extérieure</option>{tanks.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><ArrowRight size={17} /><label>Destination du transfert<select aria-label="Destination du transfert" value={targetId} onChange={event => setTargetId(event.target.value)}><option value="">Choisir une cuve</option>{tanks.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>
          <fieldset className="circuit-actuators"><legend>Pompes et vannes du circuit</legend>{actuators.map(item => <label className="check-label" key={item.id}><input type="checkbox" aria-label={`Inclure ${item.name}`} checked={actuatorIds.includes(item.id)} onChange={event => setActuatorIds(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))} /><span>{item.name}<small>{catalog.find(spec => spec.type === item.type)?.label}</small></span></label>)}{!actuators.length && <p>Ajoutez une pompe ou une vanne au P&ID, ou choisissez un modèle.</p>}</fieldset>
          {actuatorIds.length > 0 && <ol className="circuit-order" aria-label="Ordre des équipements">{actuatorIds.map((id, index) => <li key={id}><span>{index + 1}. {base.equipment.find(item => item.id === id)?.name}</span><button className="icon-button" disabled={index === 0} aria-label={`Avancer ${base.equipment.find(item => item.id === id)?.name}`} onClick={() => move(index, -1)}><ArrowUp size={15} /></button><button className="icon-button" disabled={index === actuatorIds.length - 1} aria-label={`Reculer ${base.equipment.find(item => item.id === id)?.name}`} onClick={() => move(index, 1)}><ArrowDown size={15} /></button></li>)}</ol>}
        </>}
      </div>
      <aside className="circuit-preview" aria-label="Aperçu du circuit">
        <h3>À appliquer au brouillon</h3>
        {preview.error ? <p className="inline-error" role="alert">{preview.error}</p> : <>
          <ol className="circuit-path">{preview.names.map((name, index) => <li key={index}>{name}</li>)}</ol>
          {mode === 'transfer' ? <><p>Le modèle débite {sourceId ? 'la cuve source' : 'une alimentation extérieure'} et alimente la cuve destination. Ces organes partageront un circuit en série.</p><p>{preview.removed} conduite(s) graphique(s) de ces organes seront remplacées par ce trajet. Les liaisons d’instruments sont conservées.</p><p>Les débits, temps de réponse et associations aux tags restent inchangés.</p></> : <p>{preview.names.length} équipement(s) et {preview.tagCount} tag(s) supplémentaires, sans NodeId OPC UA.</p>}
        </>}
        <p className="small-muted">Le débit en série est limité par l’organe le plus restrictif. Les branches existantes conservent leurs paramètres.</p>
      </aside>
    </div>
    {disabled && <p className="inline-error" role="alert">{stale ? 'Le projet a changé. Fermez cet aperçu et relisez le projet avant de continuer.' : 'Le projet est verrouillé. Votre sélection est conservée.'}</p>}
    <div className="modal-actions"><button className="button" onClick={onClose}>Annuler</button><button className="button primary" disabled={disabled || !preview.next} onClick={() => { if (!disabled && preview.next) { onApply(base, preview.next, preview.selectedIds); onClose(); } }}>{mode === 'duplicate' ? <Copy size={15} /> : <Route size={15} />}{mode === 'duplicate' ? 'Appliquer la copie' : 'Appliquer le circuit'}</button></div>
  </section></div>, document.body);
}
