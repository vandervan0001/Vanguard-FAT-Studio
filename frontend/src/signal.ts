import { fmt, type PreparedAction, type Scalar, type Tag } from './types';

export const OPERATORS: Record<string, string> = { eq: '=', ne: '≠', gt: '>', ge: '≥', lt: '<', le: '≤' };
export const tagReference = (tag: Tag): string => tag.plc_address || tag.plc_symbol || tag.name;
export const tagOption = (tag: Tag): string => `${tag.name} · ${tagReference(tag)} · ${tag.data_type}`;
export const signalUnit = (tag: Tag): PreparedAction['unit'] => tag.signal?.kind === '4-20mA' ? 'mA' : tag.signal?.kind === '0-10V' ? 'V' : 'native';
export const engineeringUnit = (tag: Tag): string => tag.signal?.engineering_unit ?? '%';
export function diagnosticProfile(tag: Tag, live: { value: Scalar; quality: string } | undefined): 'low' | 'high' | 'profile' | null {
  if (!tag.signal || !live || live.quality !== 'out_of_range') return null;
  const low = tag.signal.underflow_raw != null && live.value === tag.signal.underflow_raw;
  const high = tag.signal.overflow_raw != null && live.value === tag.signal.overflow_raw;
  return low && high ? 'profile' : low ? 'low' : high ? 'high' : null;
}
export const diagnosticLabel = (kind: 'low' | 'high' | 'profile'): string => kind === 'low' ? 'Diagnostic bas' : kind === 'high' ? 'Diagnostic haut' : 'Diagnostic du profil';
export function stimulusUnits(tag: Tag): [PreparedAction['unit'], string][] {
  return [['native', `Brut · ${tag.unit || tag.data_type}`], ...(tag.signal ? [['engineering', `Ingénierie · ${engineeringUnit(tag)}`], ['percent', 'Pourcentage · %'], ...(tag.signal.kind === '4-20mA' ? [['mA', 'Courant · mA']] : tag.signal.kind === '0-10V' ? [['V', 'Tension · V']] : [])] as [PreparedAction['unit'], string][] : [])];
}

// Match Python's nearest-even rounding at the declared integer signal boundary.
function roundEven(value: number): number {
  const lower = Math.floor(value);
  return value - lower === .5 ? lower % 2 === 0 ? lower : lower + 1 : Math.round(value);
}

export function nativeValue(tag: Tag, value: Scalar, unit: PreparedAction['unit'] = 'native', diagnostic = false): Scalar {
  if (tag.data_type === 'BOOL') {
    if (diagnostic) throw new Error('Les stimuli hors plage sont réservés aux entrées analogiques.');
    if (typeof value !== 'boolean' || unit !== 'native') throw new Error('Un BOOL attend TRUE ou FALSE.');
    return value;
  }
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error('Saisissez une valeur numérique finie.');
  let raw = value;
  if (unit !== 'native') {
    const kind = unit === 'mA' ? '4-20mA' : unit === 'V' ? '0-10V' : null;
    if (!tag.signal || kind && tag.signal.kind !== kind) throw new Error(`Déclarez la conversion ${kind ?? 'analogique'} dans le mapping.`);
    const low = unit === 'mA' ? 4 : unit === 'engineering' ? tag.signal.engineering_min ?? 0 : 0;
    const high = unit === 'mA' ? 20 : unit === 'V' ? 10 : unit === 'engineering' ? tag.signal.engineering_max ?? 100 : 100;
    if (!diagnostic && (value < low || value > high)) throw new Error(`Valeur attendue entre ${fmt(low)} et ${fmt(high)} ${unit === 'engineering' ? engineeringUnit(tag) : unit === 'percent' ? '%' : unit}.`);
    raw = diagnostic && unit === 'mA' && value === 0 && tag.signal.underflow_raw != null ? tag.signal.underflow_raw
      : diagnostic && unit === 'mA' && value === 24 && tag.signal.overflow_raw != null ? tag.signal.overflow_raw
      : tag.signal.raw_min + (value - low) / (high - low) * (tag.signal.raw_max - tag.signal.raw_min);
    if (tag.data_type !== 'REAL') raw = roundEven(raw);
  }
  if (tag.data_type !== 'REAL' && !Number.isInteger(raw)) throw new Error(`Une valeur ${tag.data_type} doit être entière.`);
  if (tag.data_type === 'REAL') raw = Math.fround(raw);
  const bounds = tag.data_type === 'INT' ? [-32768, 32767] : tag.data_type === 'DINT' ? [-2147483648, 2147483647] : [-3.4028234663852886e38, 3.4028234663852886e38];
  if (!Number.isFinite(raw) || raw < bounds[0] || raw > bounds[1]) throw new Error(`La valeur dépasse la plage ${tag.data_type}.`);
  const minimum = tag.min == null ? null : tag.data_type === 'REAL' ? Math.fround(tag.min) : tag.min;
  const maximum = tag.max == null ? null : tag.data_type === 'REAL' ? Math.fround(tag.max) : tag.max;
  if (!diagnostic && (minimum != null && raw < minimum || maximum != null && raw > maximum)) throw new Error(`Valeur native attendue entre ${fmt(tag.min)} et ${fmt(tag.max)} ${tag.unit}.`);
  return raw;
}

export function displayValue(tag: Tag, value: Scalar, unit: PreparedAction['unit']): Scalar {
  if (!tag.signal || typeof value !== 'number') return value;
  if (unit === 'native') return value;
  const low = unit === 'mA' ? 4 : unit === 'engineering' ? tag.signal.engineering_min ?? 0 : 0;
  const span = unit === 'mA' ? 16 : unit === 'V' ? 10 : unit === 'engineering' ? (tag.signal.engineering_max ?? 100) - low : 100;
  return low + (value - tag.signal.raw_min) / (tag.signal.raw_max - tag.signal.raw_min) * span;
}
export function electricalValue(tag: Tag, value: Scalar): Scalar { return displayValue(tag, value, signalUnit(tag)); }

export function actionPreview(tag: Tag | undefined, action: PreparedAction): string {
  if (!tag) return 'Variable à choisir';
  if (action.action === 'release') return 'Retour à la mesure du modèle';
  try {
    const raw = nativeValue(tag, action.value ?? tag.initial_value, action.unit, action.diagnostic);
    const code = action.diagnostic && action.unit === 'mA' && (action.value === 0 && tag.signal?.underflow_raw != null || action.value === 24 && tag.signal?.overflow_raw != null);
    return `${fmt(raw, 5)} ${tag.unit || 'natif'} → ${tag.data_type}${action.diagnostic ? code ? ' · diagnostic, code du profil' : ' · diagnostic hors plage' : ''}`;
  }
  catch (error) { return error instanceof Error ? error.message : String(error); }
}
