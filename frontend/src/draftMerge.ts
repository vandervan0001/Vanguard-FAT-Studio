import type { Project } from './types';

type RecordValue = Record<string, unknown>;
export type DraftChange = { key: string; path: string[]; label: string; before: unknown; local: unknown; current: unknown; conflict: boolean; kind: 'added' | 'removed' | 'changed' };
const same = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right);
const record = (value: unknown): value is RecordValue => value !== null && typeof value === 'object' && !Array.isArray(value);
const labels: Record<string, string> = { name: 'Nom', description: 'Description', simulation: 'Simulation', speed: 'Vitesse', step_ms: 'Pas de calcul', plc: 'Connexion', equipment: 'Équipements', tags: 'Variables', connections: 'Conduites', scenarios: 'Scénarios', params: 'Paramètres', bindings: 'Liaisons aux tags', position: 'Position', animation: 'Animation', unit: 'Unité', data_type: 'Type', direction: 'Sens', initial_value: 'Valeur initiale', node_id: 'NodeId', writable: 'Écriture autorisée', steps: 'Étapes', fat_steps: 'Étapes FAT', source_tank_id: 'Cuve source', tank_id: 'Cuve associée', flow_group: 'Circuit', capacity_l: 'Capacité', initial_level_pct: 'Niveau initial', min: 'Minimum', max: 'Maximum' };
const collections = new Set(['equipment', 'tags', 'connections', 'scenarios']);

/** Compare normalized projects. Only edits made in the local draft are proposed. */
export function compareDraft(base: Project, local: Project, current: Project): DraftChange[] {
  if (base.id !== local.id || local.id !== current.id) throw new Error('Ces versions ne concernent pas le même projet.');
  const changes: DraftChange[] = [];
  const visit = (before: unknown, ours: unknown, theirs: unknown, path: string[], names: string[]) => {
    if (same(before, ours) || same(ours, theirs)) return;
    if (record(before) && record(ours) && record(theirs)) {
      for (const key of new Set([...Object.keys(before), ...Object.keys(ours)])) {
        if (key === 'id' || key === 'schema_version') continue;
        visit(before[key], ours[key], theirs[key], [...path, key], [...names, labels[key] ?? key]);
      }
      return;
    }
    if (path.length === 1 && collections.has(path[0]) && Array.isArray(before) && Array.isArray(ours) && Array.isArray(theirs)) {
      for (const id of new Set([...before, ...ours].map(item => String(item.id)))) {
        const oldItem = before.find(item => item.id === id), localItem = ours.find(item => item.id === id), currentItem = theirs.find(item => item.id === id);
        visit(oldItem, localItem, currentItem, [...path, id], [...names, String(localItem?.name ?? oldItem?.name ?? id)]);
      }
      return;
    }
    changes.push({ key: JSON.stringify(path), path, label: names.join(' › '), before, local: ours, current: theirs,
      conflict: !same(before, theirs), kind: before === undefined ? 'added' : ours === undefined ? 'removed' : 'changed' });
  };
  visit(base, local, current, [], []);
  return changes;
}

/** Keep the saved project's other edits and ordering; apply only explicit choices. */
export function mergeDraft(current: Project, changes: DraftChange[], selected: Set<string>): Project {
  const result = structuredClone(current);
  for (const change of changes.filter(change => selected.has(change.key))) {
    let parent: unknown = result;
    for (const part of change.path.slice(0, -1)) {
      if (Array.isArray(parent)) parent = parent.find(item => record(item) && item.id === part);
      else if (record(parent) && Object.prototype.hasOwnProperty.call(parent, part)) parent = parent[part];
      else throw new Error('Une référence a changé. Fermez la comparaison et relisez le projet.');
    }
    const key = change.path.at(-1)!;
    if (Array.isArray(parent)) {
      const index = parent.findIndex(item => record(item) && item.id === key);
      if (change.local === undefined) { if (index >= 0) parent.splice(index, 1); }
      else if (index < 0) parent.push(structuredClone(change.local));
      else parent[index] = structuredClone(change.local);
    } else if (record(parent)) {
      if (change.local === undefined) delete parent[key];
      else Object.defineProperty(parent, key, { value: structuredClone(change.local), writable: true, enumerable: true, configurable: true });
    } else throw new Error('Le champ à reprendre n’existe plus. Relisez le projet.');
  }
  return result;
}

export function draftValue(value: unknown): string {
  if (value === undefined) return 'Absent';
  if (value === null) return 'Aucun';
  if (typeof value === 'boolean') return value ? 'Oui' : 'Non';
  if (typeof value === 'string') return value || '(vide)';
  return JSON.stringify(value, null, 2);
}

/** Collection indices can move during a merge; identify an error by its entity. */
export function draftErrorKey(project: Project, error: { path: string; message: string }): string {
  let parent: unknown = project;
  const path = error.path.split('.').map(part => {
    if (Array.isArray(parent) && /^\d+$/.test(part)) {
      parent = parent[Number(part)];
      return record(parent) && typeof parent.id === 'string' ? `id:${parent.id}` : `value:${JSON.stringify(parent)}`;
    }
    parent = record(parent) && Object.prototype.hasOwnProperty.call(parent, part) ? parent[part] : undefined;
    return part;
  });
  return JSON.stringify([path, error.message]);
}
