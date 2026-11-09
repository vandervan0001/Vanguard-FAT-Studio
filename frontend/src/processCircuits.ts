import { makeEquipment, missingPortTags, nextEquipmentName } from './pidBuilder';
import { uid, type CatalogItem, type Equipment, type Project, type Scenario, type Tag } from './types';

export type CircuitTemplate = 'fill' | 'drain' | 'transfer' | 'vfd';
export const CIRCUIT_TEMPLATES: { id: CircuitTemplate; name: string; description: string }[] = [
  { id: 'fill', name: 'Remplissage', description: 'Une cuve, une pompe et une vanne depuis une alimentation extérieure.' },
  { id: 'drain', name: 'Vidange', description: 'Une cuve et une vanne modulante vers une sortie extérieure.' },
  { id: 'transfer', name: 'Transfert entre cuves', description: 'Deux cuves, une pompe et une vanne. Le volume sortant alimente la destination.' },
  { id: 'vfd', name: 'Pompe à variateur', description: 'Une cuve, une pompe à variateur et une vanne avec consigne de vitesse.' },
];
export const isFlowEquipment = (item: Equipment) => ['pump', 'pump_vfd', 'valve_onoff', 'valve_control'].includes(item.type);
const resolved = (item: Equipment, catalog: CatalogItem[]) => ({ ...catalog.find(spec => spec.type === item.type)?.default_params, ...item.params });
function groupKey(item: Equipment, catalog: CatalogItem[]) {
  const params = resolved(item, catalog);
  return isFlowEquipment(item) && params.tank_id && params.flow_group ? JSON.stringify([params.tank_id, params.role, params.flow_group]) : '';
}
function checkLimits(project: Project) {
  if (project.equipment.length > 50) throw new Error('Le projet est limité à 50 équipements.');
  if (project.tags.length > 200) throw new Error('Le projet est limité à 200 tags.');
  if (project.connections.length > 200) throw new Error('Le projet est limité à 200 liaisons.');
  if (project.scenarios.length > 100) throw new Error('Le projet est limité à 100 scénarios.');
  if (project.equipment.some(item => Math.abs(item.position.x) > 100000 || Math.abs(item.position.y) > 100000)) throw new Error('Le placement dépasserait la surface du dessin. Rapprochez les équipements avant de continuer.');
}

export type TransferChoice = { sourceId: string; targetId: string; actuatorIds: string[] };
export function planTransfer(project: Project, catalog: CatalogItem[], choice: TransferChoice) {
  const { sourceId, targetId, actuatorIds } = choice;
  const target = project.equipment.find(item => item.id === targetId && item.type === 'tank');
  const source = project.equipment.find(item => item.id === sourceId && item.type === 'tank');
  if (!target || (sourceId && !source)) throw new Error('Choisissez les cuves présentes dans le projet.');
  if (sourceId === targetId) throw new Error('La source et la destination doivent être deux cuves différentes.');
  if (!actuatorIds.length) throw new Error('Choisissez au moins une pompe ou une vanne.');
  if (new Set(actuatorIds).size !== actuatorIds.length) throw new Error('Un équipement ne peut apparaître qu’une fois dans le circuit.');
  const actuators = actuatorIds.map(id => project.equipment.find(item => item.id === id));
  if (actuators.some(item => !item || !isFlowEquipment(item))) throw new Error('Le circuit accepte uniquement des pompes et des vannes en série.');
  const selected = new Set(actuatorIds);
  const previousGroups = new Set(actuators.map(item => groupKey(item!, catalog)).filter(Boolean));
  const leftBehind = project.equipment.filter(item => !selected.has(item.id) && previousGroups.has(groupKey(item, catalog)));
  if (leftBehind.length) throw new Error(`Ajoutez aussi ${leftBehind.map(item => item.name).join(', ')} : ces équipements partagent le circuit actuel. Vous pourrez ensuite modifier l’ensemble.`);
  const flowGroup = uid('transfert');
  const equipment = project.equipment.map(item => selected.has(item.id) ? { ...item, params: { ...item.params, tank_id: targetId, source_tank_id: sourceId, role: 'inlet', flow_group: flowGroup } } : item);
  const physicalIds = new Set(project.equipment.filter(item => item.type === 'tank' || isFlowEquipment(item)).map(item => item.id));
  const removed = project.connections.filter(line => (selected.has(line.source) || selected.has(line.target)) && physicalIds.has(line.source) && physicalIds.has(line.target));
  const removedIds = new Set(removed.map(line => line.id));
  const path = [...(sourceId ? [sourceId] : []), ...actuatorIds, targetId];
  const lines = path.slice(1).map((id, index) => ({ id: uid('line'), source: path[index], target: id, label: sourceId ? 'Transfert' : 'Remplissage', directed: true }));
  const next = { ...project, equipment, connections: [...project.connections.filter(line => !removedIds.has(line.id)), ...lines] };
  checkLimits(next);
  return { project: next, sourceName: source?.name ?? 'Alimentation extérieure', targetName: target.name, actuatorNames: actuators.map(item => item!.name), removed, added: lines, selectedIds: actuatorIds };
}

function suggestedScenario(kind: CircuitTemplate, equipment: Equipment[]): Scenario {
  const name = CIRCUIT_TEMPLATES.find(item => item.id === kind)!.name;
  const tanks = equipment.filter(item => item.type === 'tank');
  return {
    id: uid('fat'), name: `${name} · trame à relire`, description: 'Trame d’observation proposée. Adapter les conditions, commandes et résultats attendus au programme testé avant exécution.',
    execution_mode: 'guided', duration_s: 60, steps: [], preconditions: 'Vérifier les paramètres du circuit et les états initiaux. Préparer la commande dans le contrôleur de démonstration ou le programme PLC de test.',
    focus_equipment: equipment.map(item => item.id), trend_tags: tanks.map(item => item.bindings.level).filter(Boolean),
    fat_steps: [
      { id: uid('step'), name: 'État initial', instructions: `Relever les niveaux de ${tanks.map(item => item.name).join(' et ')} et les positions des organes.`, expected_result: 'Les niveaux et états correspondent aux conditions initiales prévues par le testeur.', actions: [], checks: [] },
      { id: uid('step'), name: 'Écoulement', instructions: 'Demander le fonctionnement du circuit avec les commandes prévues pour le programme testé, puis observer les niveaux et les retours.', expected_result: kind === 'transfer' ? 'Le niveau source baisse et le niveau destination augmente pendant le transfert.' : kind === 'drain' ? 'Le niveau de la cuve baisse lorsque la vidange est ouverte.' : 'Le niveau de la cuve augmente lorsque le circuit alimente la cuve.', actions: [], checks: [] },
      { id: uid('step'), name: 'Fin de transfert', instructions: 'Demander l’arrêt du circuit avec les commandes prévues, puis vérifier les retours et le débit après le temps de réponse.', expected_result: 'Les organes rejoignent les états attendus et le débit du circuit devient nul.', actions: [], checks: [] },
    ],
  };
}

export function insertCircuit(project: Project, catalog: CatalogItem[], kind: CircuitTemplate, withScenario = false) {
  if (!CIRCUIT_TEMPLATES.some(item => item.id === kind)) throw new Error('Modèle de circuit inconnu.');
  const equipment: Equipment[] = [];
  const tags: Tag[] = [];
  const offset = project.equipment.length ? Math.max(...project.equipment.map(item => item.position.y)) + 340 : 0;
  const add = (type: Equipment['type'], x: number, y: number) => {
    const spec = catalog.find(item => item.type === type);
    if (!spec) throw new Error('Le catalogue ne contient pas les équipements de ce circuit.');
    const item = makeEquipment(spec, [...project.equipment, ...equipment], { x, y: y + offset });
    const created = missingPortTags(item, spec); item.bindings = created.bindings;
    equipment.push(item); tags.push(...created.tags); return item;
  };
  const source = kind === 'transfer' ? add('tank', 0, 0) : undefined;
  if (source) source.params.initial_level_pct = 65;
  const tank = add('tank', kind === 'transfer' ? 700 : kind === 'drain' ? 0 : 440, 0);
  if (kind === 'drain') tank.params.initial_level_pct = 75;
  const pump = kind !== 'drain' ? add(kind === 'vfd' ? 'pump_vfd' : 'pump', kind === 'transfer' ? 240 : 0, 240) : undefined;
  const valve = add(kind === 'drain' ? 'valve_control' : 'valve_onoff', kind === 'transfer' ? 460 : 220, 240);
  const flowGroup = uid(kind);
  for (const item of [pump, valve].filter((item): item is Equipment => Boolean(item))) item.params = { ...item.params, tank_id: tank.id, source_tank_id: source?.id ?? '', role: kind === 'drain' ? 'outlet' : 'inlet', flow_group: flowGroup };
  const path = kind === 'drain' ? [tank.id, valve.id] : [...(source ? [source.id] : []), pump!.id, valve.id, tank.id];
  const lines = path.slice(1).map((id, index) => ({ id: uid('line'), source: path[index], target: id, label: CIRCUIT_TEMPLATES.find(item => item.id === kind)!.name, directed: true }));
  const next: Project = { ...project, equipment: [...project.equipment, ...equipment], tags: [...project.tags, ...tags], connections: [...project.connections, ...lines], scenarios: withScenario ? [...project.scenarios, suggestedScenario(kind, equipment)] : project.scenarios };
  checkLimits(next);
  return { project: next, addedEquipment: equipment, addedTags: tags, selectedIds: equipment.map(item => item.id) };
}

/** A circuit includes its complete physical flow group, tanks and attached sensors. */
export function circuitMembers(project: Project, catalog: CatalogItem[], equipmentId: string) {
  const chosen = project.equipment.find(item => item.id === equipmentId);
  if (!chosen) return [];
  const key = groupKey(chosen, catalog);
  if (!key) return [chosen];
  const members = new Set(project.equipment.filter(item => groupKey(item, catalog) === key).map(item => item.id));
  for (const item of project.equipment.filter(item => members.has(item.id))) {
    const params = resolved(item, catalog);
    for (const field of ['tank_id', 'source_tank_id']) if (typeof params[field] === 'string' && project.equipment.some(entry => entry.id === params[field] && entry.type === 'tank')) members.add(params[field] as string);
  }
  for (const item of project.equipment) if (['analog_sensor', 'digital_sensor'].includes(item.type) && members.has(String(resolved(item, catalog).source_equipment))) members.add(item.id);
  return project.equipment.filter(item => members.has(item.id));
}

export function duplicateEquipment(project: Project, catalog: CatalogItem[], equipmentId: string, wholeCircuit: boolean) {
  const source = wholeCircuit ? circuitMembers(project, catalog, equipmentId) : project.equipment.filter(item => item.id === equipmentId);
  if (!source.length) throw new Error('L’équipement à dupliquer n’existe plus.');
  const ids = new Map(source.map(item => [item.id, uid(item.type)]));
  const equipment: Equipment[] = [];
  const tags: Tag[] = [];
  const tagIds = new Map<string, string>();
  const groups = new Map<string, string>();
  const minY = Math.min(...source.map(item => item.position.y));
  const offset = Math.max(...project.equipment.map(item => item.position.y)) - minY + 340;
  for (const original of source) {
    const name = nextEquipmentName(original.type, [...project.equipment, ...equipment]);
    const params = { ...original.params };
    for (const field of ['tank_id', 'source_tank_id', 'source_equipment']) if (typeof params[field] === 'string') params[field] = ids.get(params[field] as string) ?? '';
    const key = groupKey(original, catalog);
    if (isFlowEquipment(original)) { if (!groups.has(key)) groups.set(key, uid('copie')); params.flow_group = groups.get(key)!; }
    const bindings: Record<string, string> = {};
    const cloneTag = (tagId: string) => {
      const tag = project.tags.find(tag => tag.id === tagId);
      if (!tag) return undefined;
      if (!tagIds.has(tag.id)) {
        const id = uid('tag'); tagIds.set(tag.id, id);
        tags.push({ ...tag, id, name: `${name}.${Object.entries(original.bindings).find(([, value]) => value === tagId)?.[0] ?? 'animation'}`, node_id: '', plc_address: '', plc_symbol: '', ...(tag.signal ? { signal: { ...tag.signal } } : {}) });
      }
      return tagIds.get(tagId)!;
    };
    for (const [port, tagId] of Object.entries(original.bindings)) { const id = cloneTag(tagId); if (id) bindings[port] = id; }
    const animationTag = original.animation ? cloneTag(original.animation.tag_id) : undefined;
    equipment.push({ ...original, id: ids.get(original.id)!, name, params, bindings, position: { x: original.position.x, y: original.position.y + offset }, animation: original.animation && animationTag ? { ...original.animation, tag_id: animationTag } : null });
  }
  const connections = project.connections.filter(line => ids.has(line.source) && ids.has(line.target)).map(line => ({ ...line, id: uid('line'), source: ids.get(line.source)!, target: ids.get(line.target)! }));
  const next = { ...project, equipment: [...project.equipment, ...equipment], tags: [...project.tags, ...tags], connections: [...project.connections, ...connections] };
  checkLimits(next);
  return { project: next, addedEquipment: equipment, addedTags: tags, selectedIds: equipment.map(item => item.id) };
}
