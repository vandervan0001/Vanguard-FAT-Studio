import { uid, type CatalogItem, type Equipment, type EquipmentType, type Project, type Tag } from './types';

export type Port = CatalogItem['ports'][string];
const prefixes: Record<EquipmentType, string> = { tank: 'TK', pump: 'P', pump_vfd: 'VFD', valve_onoff: 'XV', valve_control: 'CV', analog_sensor: 'AI', digital_sensor: 'DI', digital_input: 'PB', indicator: 'ST' };

export function nextEquipmentName(type: EquipmentType, equipment: Equipment[]) {
  const names = new Set(equipment.map(item => item.name.split(' · ')[0].trim().toUpperCase()));
  let number = 101;
  while (names.has(`${prefixes[type]}-${number}`)) number++;
  return `${prefixes[type]}-${number}`;
}

export function freePosition(equipment: Equipment[], desired: Equipment['position']) {
  const origin = { x: Math.round(desired.x / 20) * 20, y: Math.round(desired.y / 20) * 20 };
  // Search around the visible centre, using the symbol footprint plus breathing room.
  for (let radius = 0; radius < 12; radius++) {
    for (let y = -radius; y <= radius; y++) for (let x = -radius; x <= radius; x++) {
      if (Math.max(Math.abs(x), Math.abs(y)) !== radius) continue;
      const position = { x: origin.x + x * 220, y: origin.y + y * 240 };
      if (!equipment.some(item => Math.abs(item.position.x - position.x) < 190 && Math.abs(item.position.y - position.y) < 210)) return position;
    }
  }
  return { x: Math.max(origin.x, ...equipment.map(item => item.position.x)) + 220, y: origin.y };
}

export function makeEquipment(item: CatalogItem, equipment: Equipment[], position: Equipment['position']): Equipment {
  return { id: uid(item.type), type: item.type, name: nextEquipmentName(item.type, equipment), description: '', unit: '', position, params: { ...item.default_params }, bindings: {} };
}

export function makePortTag(equipment: Equipment, port: string, spec: Port, dataType = spec.data_types[0] as Tag['data_type']): Tag {
  const unit = spec.unit ?? '';
  return { id: uid(`${equipment.id}_${port}`), name: `${equipment.name}.${port}`, direction: spec.direction, data_type: dataType, unit,
    initial_value: dataType === 'BOOL' ? false : 0, min: dataType === 'BOOL' ? null : 0, max: unit === '%' ? 100 : null,
    node_id: '', writable: spec.direction === 'input' };
}

export function missingPortTags(equipment: Equipment, item: CatalogItem) {
  const bindings = { ...equipment.bindings };
  const tags = Object.entries(item.ports).filter(([port]) => !bindings[port]).map(([port, spec]) => {
    const tag = makePortTag(equipment, port, spec); bindings[port] = tag.id; return tag;
  });
  return { bindings, tags };
}

export function fillCircuit(project: Project, catalog: CatalogItem[]) {
  if (project.equipment.length) throw new Error('Le circuit de départ nécessite un P&ID vide.');
  const group = uid('remplissage');
  const equipment: Equipment[] = [];
  const tags: Tag[] = [];
  for (const [type, position] of [['tank', { x: 480, y: 80 }], ['pump', { x: 40, y: 300 }], ['valve_onoff', { x: 260, y: 300 }]] as const) {
    const item = catalog.find(item => item.type === type);
    if (!item) throw new Error('Le catalogue ne contient pas les équipements du circuit de départ.');
    const entry = makeEquipment(item, equipment, position);
    if (type !== 'tank') entry.params = { ...entry.params, tank_id: equipment[0].id, flow_group: group, role: 'inlet' };
    const created = missingPortTags(entry, item); entry.bindings = created.bindings;
    tags.push(...created.tags); equipment.push(entry);
  }
  if (project.tags.length + tags.length > 200) throw new Error('Le circuit dépasserait la limite de 200 tags.');
  const [tank, pump, valve] = equipment;
  return { ...project, equipment, tags: [...project.tags, ...tags], connections: [
    { id: uid('line'), source: pump.id, target: valve.id, label: 'Alimentation', directed: true },
    { id: uid('line'), source: valve.id, target: tank.id, label: 'Remplissage', directed: true },
  ] };
}

export const compatibleTag = (tag: Tag, spec: Port) => tag.direction === spec.direction && spec.data_types.includes(tag.data_type);

/** Only physical input producers are exclusive. Manual requests and PLC reads can share a tag. */
export function bindingOwners(project: Project, equipment: Equipment, bindings: Equipment['bindings'], port: string, catalog: CatalogItem[], tagId: string) {
  const spec = catalog.find(item => item.type === equipment.type)?.ports[port];
  if (spec?.direction !== 'input' || spec.simulated_source === false) return [];
  return project.equipment.flatMap(entry => {
    const ports = catalog.find(item => item.type === entry.type)?.ports ?? {};
    return Object.entries(entry.id === equipment.id ? bindings : entry.bindings)
      .filter(([key, id]) => id === tagId && !(entry.id === equipment.id && key === port) && ports[key]?.direction === 'input' && ports[key]?.simulated_source !== false)
      .map(([key]) => `${entry.name} · ${ports[key]?.label ?? key}`);
  });
}

const aliases: Record<string, string[]> = {
  command: ['command', 'runcommand', 'commande', 'marche', 'cmd'], feedback: ['feedback', 'running', 'runfeedback', 'retourmarche'],
  fault: ['fault', 'defaut'], speed_command: ['speedcommand', 'consignevitesse'], speed: ['speedfeedback', 'speed', 'vitesse'],
  manual_request: ['request', 'manualrequest', 'demande'], manual_speed: ['requestedspeed', 'manualspeed'],
  position: ['position', 'positionfeedback'], open: ['open', 'ouvert'], closed: ['closed', 'ferme'],
  level: ['level', 'niveau'], volume: ['volume'], high: ['high', 'niveauhaut'], low: ['low', 'niveaubas'],
  value: ['value', 'raw', 'valeur'], scaled_value: ['scaledvalue', 'percent', 'engineeringvalue'],
};
const normalized = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '');

/** Suggestions use names/symbols only, never Siemens addresses, NodeIds or analog scales. */
export function suggestBindings(project: Project, equipment: Equipment, item: CatalogItem, catalog: CatalogItem[], current: Equipment['bindings']) {
  const bindings = { ...current };
  const match = equipment.name.match(/^\s*([a-z]+)[\s_-]*(\d+)\b/i);
  if (!match) return bindings;
  const reference = normalized(match[1] + match[2]);
  for (const [port, spec] of Object.entries(item.ports)) {
    if (bindings[port]) continue;
    const ranked = project.tags.filter(tag => compatibleTag(tag, spec) && !bindingOwners(project, equipment, bindings, port, catalog, tag.id).length).map(tag => {
      const scores = [tag.name, tag.plc_symbol ?? ''].map(name => {
        const value = normalized(name); const at = value.indexOf(reference);
        if (at < 0 || /\d/.test(value[at + reference.length] ?? '')) return 0;
        const suffix = value.slice(at + reference.length);
        return (aliases[port] ?? [port]).some(alias => suffix === normalized(alias)) ? 1 : 0;
      });
      return { tag, score: Math.max(...scores) };
    }).filter(candidate => candidate.score > 0);
    // Ambiguous names require an explicit user choice; list order is not evidence.
    if (ranked.length === 1) bindings[port] = ranked[0].tag.id;
  }
  return bindings;
}
