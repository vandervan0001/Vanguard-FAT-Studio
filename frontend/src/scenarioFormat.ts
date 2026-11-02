import type { ScenarioStep } from './types';

const ACTIONS = new Set(['force', 'release', 'fault', 'clear_fault', 'marker', 'expect']);
const OPERATORS = new Set(['eq', 'ne', 'gt', 'ge', 'lt', 'le']);
const FIELDS = new Set(['at_s', 'action', 'target', 'value', 'operator', 'tolerance', 'message']);
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const scalar = (value: unknown) => value === null || typeof value === 'boolean' || typeof value === 'string' || (typeof value === 'number' && Number.isFinite(value));

/** Validate the editable JSON before putting untrusted values into JSX state.
 * The server remains authoritative for tag types, permissions and references.
 */
export function parseScenarioSteps(text: string, duration: number): ScenarioStep[] {
  if (text.length > 1_000_000) throw new Error('Les étapes dépassent la taille maximale de 1 Mo.');
  const data: unknown = JSON.parse(text);
  if (!Array.isArray(data)) throw new Error('Les étapes doivent être un tableau JSON.');
  if (data.length > 2000) throw new Error('Un scénario accepte au maximum 2 000 étapes.');
  let previous = -1;
  for (const [index, step] of data.entries()) {
    const fail = (reason: string): never => { throw new Error(`Étape ${index + 1} : ${reason}`); };
    if (!isRecord(step)) fail('une étape doit être un objet JSON.');
    const item = step as Record<string, unknown>;
    const unknownFields = Object.keys(item).filter(key => !FIELDS.has(key));
    if (unknownFields.length) fail(`champ(s) inconnu(s) : ${unknownFields.join(', ')}.`);
    if (typeof item.at_s !== 'number' || !Number.isFinite(item.at_s) || item.at_s < 0 || item.at_s > duration) fail('at_s doit être un temps fini compris entre 0 et la durée du scénario.');
    const time = item.at_s as number;
    if (time < previous) fail('les étapes doivent être classées par temps croissant.');
    previous = time;
    if (typeof item.action !== 'string' || !ACTIONS.has(item.action)) fail('action inconnue.');
    if (item.target !== undefined && (typeof item.target !== 'string' || item.target.length > 80)) fail('target doit être un identifiant texte de 80 caractères maximum.');
    if (item.action !== 'marker' && !item.target) fail('target est obligatoire pour cette action.');
    if (item.message !== undefined && (typeof item.message !== 'string' || item.message.length > 4000)) fail('message doit être du texte de 4 000 caractères maximum.');
    if (item.operator !== undefined && (typeof item.operator !== 'string' || !OPERATORS.has(item.operator))) fail('operator doit être eq, ne, gt, ge, lt ou le.');
    if (item.tolerance !== undefined && (typeof item.tolerance !== 'number' || !Number.isFinite(item.tolerance) || item.tolerance < 0 || item.tolerance > 1e9)) fail('tolerance doit être un nombre fini positif ou nul.');
    if (item.value !== undefined && !scalar(item.value)) {
      if (!isRecord(item.value) || typeof item.value.kind !== 'string' || Object.keys(item.value).some(key => !['kind', 'value'].includes(key))) fail('value doit être un scalaire ou un objet de défaut {kind, value?}.');
      const fault = item.value as Record<string, unknown>;
      if (fault.value !== undefined && fault.value !== null && !(typeof fault.value === 'boolean' || (typeof fault.value === 'number' && Number.isFinite(fault.value)))) fail('la valeur du défaut doit être numérique ou booléenne.');
    }
    if (item.action === 'fault' && (!isRecord(item.value) || typeof item.value.kind !== 'string')) fail('un défaut doit préciser value: {"kind": "type_de_défaut"}.');
  }
  return data as ScenarioStep[];
}
