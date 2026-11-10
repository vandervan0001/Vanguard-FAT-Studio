import { circuitMembers, copyEquipmentInto, isFlowEquipment } from './processCircuits';
import { uid, type CatalogItem, type Equipment, type Project, type Tag } from './types';

export const CIRCUIT_LIBRARY_KEY = 'vanguard:circuits:1';
const MAX_LIBRARY_BYTES = 2 * 1024 * 1024;
export type SavedCircuit = { version: 1; id: string; name: string; createdAt: string; anchorId: string;
  equipment: Equipment[]; tags: Tag[]; connections: Project['connections'] };
const object = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === 'object' && !Array.isArray(value);
const text = (value: unknown, max = 200): value is string => typeof value === 'string' && value.length <= max;
const id = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z][A-Za-z0-9_-]{0,79}$/.test(value);
const number = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const scalar = (value: unknown) => typeof value === 'boolean' || number(value);

/** Local storage is untrusted. The canonical server preview checks semantics before insertion. */
export function readSavedCircuits(): SavedCircuit[] {
  const raw = localStorage.getItem(CIRCUIT_LIBRARY_KEY);
  if (!raw) return [];
  return parseSavedCircuits(raw);
}
export function parseSavedCircuits(raw: string): SavedCircuit[] {
  if (raw.length > MAX_LIBRARY_BYTES || new TextEncoder().encode(raw).byteLength > MAX_LIBRARY_BYTES) throw new Error('La bibliothèque locale dépasse 2 Mio. Ses données sont conservées.');
  let values: unknown;
  try { values = JSON.parse(raw); } catch { throw new Error('La bibliothèque locale est illisible. Téléchargez-la avant de la réinitialiser.'); }
  if (!Array.isArray(values) || values.length > 20 || values.some(value => !validCircuit(value))) throw new Error('La bibliothèque locale est illisible. Téléchargez-la avant de la réinitialiser.');
  if (new Set(values.map(value => value.id)).size !== values.length) throw new Error('La bibliothèque contient des identifiants dupliqués. Ses données sont conservées.');
  return values.map(cleanCircuit);
}
function validCircuit(value: unknown): value is SavedCircuit {
  if (!object(value) || value.version !== 1 || !id(value.id) || !text(value.name) || !value.name.trim() || !text(value.createdAt) || !Number.isFinite(Date.parse(value.createdAt)) || !id(value.anchorId)) return false;
  if (!Array.isArray(value.equipment) || !value.equipment.length || value.equipment.length > 50 || !Array.isArray(value.tags) || value.tags.length > 200 || !Array.isArray(value.connections) || value.connections.length > 200) return false;
  if (value.equipment.some(item => !object(item) || !id(item.id) || !text(item.name) || !['tank', 'pump', 'pump_vfd', 'valve_onoff', 'valve_control', 'analog_sensor', 'digital_sensor', 'digital_input', 'indicator'].includes(String(item.type)) || !object(item.params) || !object(item.bindings) || Object.values(item.bindings).some(value => !id(value)) || !object(item.position) || !number(item.position.x) || !number(item.position.y) || (item.animation != null && !object(item.animation)))) return false;
  if (value.tags.some(item => !object(item) || !id(item.id) || !text(item.name) || !['input', 'output'].includes(String(item.direction)) || !['BOOL', 'INT', 'DINT', 'REAL'].includes(String(item.data_type)) || !scalar(item.initial_value) || !text(item.unit) || typeof item.writable !== 'boolean' || (item.signal != null && !object(item.signal)))) return false;
  if (value.connections.some(item => !object(item) || !id(item.id) || !id(item.source) || !id(item.target) || !text(item.label) || typeof item.directed !== 'boolean')) return false;
  const equipmentIds = new Set(value.equipment.map(item => item.id));
  const tagIds = new Set(value.tags.map(item => item.id));
  return equipmentIds.size === value.equipment.length && tagIds.size === value.tags.length && value.equipment.some(item => item.id === value.anchorId && isFlowEquipment(item))
    && value.connections.every(line => equipmentIds.has(line.source) && equipmentIds.has(line.target));
}
function cleanCircuit(value: SavedCircuit): SavedCircuit {
  const selected = new Set(value.equipment.map(item => item.id));
  return {
    version: 1, id: value.id, name: value.name, createdAt: value.createdAt, anchorId: value.anchorId,
    equipment: value.equipment.map(item => {
      const params = { ...item.params };
      for (const field of ['tank_id', 'source_tank_id', 'source_equipment']) if (typeof params[field] === 'string' && !selected.has(params[field] as string)) params[field] = '';
      return { id: item.id, name: item.name, type: item.type, description: item.description ?? '', unit: item.unit ?? '', position: { ...item.position }, params,
        bindings: { ...item.bindings }, animation: item.animation ? { ...item.animation } : null };
    }),
    tags: value.tags.map(tag => ({ id: tag.id, name: tag.name, direction: tag.direction, data_type: tag.data_type, unit: tag.unit, initial_value: tag.initial_value,
      min: tag.min, max: tag.max, writable: tag.writable, node_id: '', plc_address: '', plc_symbol: '', signal: tag.signal ? { ...tag.signal } : null })),
    connections: value.connections.map(line => ({ id: line.id, source: line.source, target: line.target, label: line.label, directed: line.directed })),
  };
}
export function makeSavedCircuit(project: Project, catalog: CatalogItem[], anchorId: string, name: string): SavedCircuit {
  const anchor = project.equipment.find(item => item.id === anchorId);
  if (!anchor || !isFlowEquipment(anchor)) throw new Error('Sélectionnez une pompe ou une vanne pour enregistrer son circuit.');
  if (!name.trim() || name.trim().length > 200) throw new Error('Donnez un nom de 1 à 200 caractères au circuit.');
  const equipment = circuitMembers(project, catalog, anchorId);
  const selected = new Set(equipment.map(item => item.id));
  const tagIds = new Set(equipment.flatMap(item => [...Object.values(item.bindings), ...(item.animation ? [item.animation.tag_id] : [])]));
  return cleanCircuit({ version: 1, id: uid('circuit'), name: name.trim(), createdAt: new Date().toISOString(), anchorId, equipment,
    tags: project.tags.filter(tag => tagIds.has(tag.id)), connections: project.connections.filter(line => selected.has(line.source) && selected.has(line.target)) });
}
export function insertSavedCircuit(project: Project, catalog: CatalogItem[], saved: SavedCircuit) {
  if (!validCircuit(saved)) throw new Error('Le modèle de circuit est illisible. Aucun changement appliqué.');
  const clean = cleanCircuit(saved);
  return copyEquipmentInto(project, catalog, { ...project, equipment: clean.equipment, tags: clean.tags, connections: clean.connections, scenarios: [] }, clean.anchorId, true);
}
export function saveCircuit(saved: SavedCircuit) {
  const entries = readSavedCircuits();
  if (entries.length >= 20) throw new Error('La bibliothèque est limitée à 20 circuits. Retirez un modèle avant d’en ajouter un.');
  if (!validCircuit(saved)) throw new Error('Le circuit est illisible. Aucun modèle enregistré.');
  if (entries.some(item => item.name.toLocaleLowerCase() === saved.name.toLocaleLowerCase())) throw new Error('Ce nom existe déjà dans la bibliothèque. Choisissez un autre nom.');
  writeCircuits([...entries, cleanCircuit(saved)]);
}
function writeCircuits(entries: SavedCircuit[]) {
  const raw = JSON.stringify(entries);
  if (raw.length > MAX_LIBRARY_BYTES || new TextEncoder().encode(raw).byteLength > MAX_LIBRARY_BYTES) throw new Error('La bibliothèque dépasserait 2 Mio. Aucun modèle enregistré.');
  try { localStorage.setItem(CIRCUIT_LIBRARY_KEY, raw); }
  catch { throw new Error('Le navigateur ne peut pas enregistrer la bibliothèque. Le projet et les modèles précédents sont conservés.'); }
}
export function removeSavedCircuit(circuitId: string) { writeCircuits(readSavedCircuits().filter(item => item.id !== circuitId)); }

export function planLibraryImport(existing: SavedCircuit[], incoming: SavedCircuit[]) {
  const additions: SavedCircuit[] = [];
  let unchanged = 0;
  for (const item of incoming) {
    const same = existing.find(old => old.id === item.id);
    if (same && JSON.stringify(cleanCircuit(same)) === JSON.stringify(cleanCircuit(item))) { unchanged++; continue; }
    if (same || [...existing, ...additions].some(old => old.name.toLocaleLowerCase() === item.name.toLocaleLowerCase())) throw new Error(`Le modèle « ${item.name} » existe déjà avec un contenu ou un identifiant différent. Aucun modèle ne sera remplacé.`);
    additions.push(cleanCircuit(item));
  }
  if (existing.length + additions.length > 20) throw new Error('Cet import dépasserait la limite de 20 circuits. Aucun modèle ne sera remplacé.');
  return { additions, unchanged };
}
export function importSavedCircuits(incoming: SavedCircuit[], expectedRaw: string | null) {
  if (localStorage.getItem(CIRCUIT_LIBRARY_KEY) !== expectedRaw) throw new Error('La bibliothèque a changé dans un autre onglet. Relisez le fichier avant de l’importer.');
  const existing = readSavedCircuits();
  const plan = planLibraryImport(existing, incoming);
  writeCircuits([...existing, ...plan.additions]);
}
