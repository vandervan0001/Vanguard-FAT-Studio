export type Scalar = number | boolean;
export type EquipmentType = 'tank' | 'pump' | 'valve_onoff' | 'valve_control' | 'analog_sensor' | 'digital_sensor' | 'indicator';
export type Parameter = string | number | boolean;
export type Equipment = {
  id: string; type: EquipmentType; name: string; description: string; unit: string;
  position: { x: number; y: number }; params: Record<string, Parameter>; bindings: Record<string, string>;
};
export type ProcessConnection = { id: string; source: string; target: string; label: string; directed: boolean };
export type Tag = {
  id: string; name: string; direction: 'input' | 'output'; data_type: 'BOOL' | 'INT' | 'DINT' | 'REAL';
  unit: string; initial_value: Scalar; min: number | null; max: number | null; node_id: string; writable: boolean;
};
export type ScenarioStep = {
  at_s: number; action: 'force' | 'release' | 'fault' | 'clear_fault' | 'marker' | 'expect';
  target?: string; value?: unknown; operator?: 'eq' | 'ne' | 'gt' | 'ge' | 'lt' | 'le'; tolerance?: number; message?: string;
};
export type Scenario = { id: string; name: string; description: string; duration_s: number; steps: ScenarioStep[] };
export type ScenarioDraft = { scenarioId: string; text: string };
export type PLCConfig = {
  mode: 'demo' | 'opcua'; tia_version: 'V20' | 'V21'; endpoint: string; expected_application_uri: string; namespace_uri: string;
  security_policy: 'None' | 'Basic256Sha256'; server_certificate_sha256: string; client_certificate: string;
  client_private_key: string; username_env: string; password_env: string; approved_virtual_target: string; timeout_s: number;
};
export type Project = {
  schema_version: '1.0'; id: string; name: string; description: string;
  simulation: { step_ms: number; speed: number }; equipment: Equipment[]; connections: ProcessConnection[];
  tags: Tag[]; scenarios: Scenario[]; plc: PLCConfig;
};
export type CatalogItem = {
  type: EquipmentType; label: string; description: string; default_params: Record<string, Parameter>;
  ports: Record<string, { label: string; direction: 'input' | 'output'; data_types: string[]; required: boolean; unit?: string }>;
  parameters: Record<string, { label: string; type: 'number' | 'string' | 'boolean' | 'select'; min?: number; max?: number; options?: (string | {value: string; label: string})[]; unit?: string }>;
};
export type Validation = { valid: boolean; errors: { path: string; message: string }[]; warnings: { path: string; message: string }[] };
export type Event = { id: string | number; timestamp: string; sim_time_s: number; kind: string; message: string };
export type RunResult = { verdict: 'not_evaluated' | 'pass' | 'fail'; comment: string };
export type ReportDraft = RunResult & { runId: string | null; marker: string; resultDirty: boolean; saved: boolean };
export type Snapshot = {
  project_id: string;
  project_revision: string;
  status: 'idle' | 'running' | 'paused' | 'stopped' | 'error'; sim_time_s: number; wall_time: string; run_id: string | null;
  connection: { mode: string; connected: boolean; target: string; quality: string; last_update: string | null; error: string | null };
  tags: Record<string, { value: Scalar; quality: string; forced: boolean }>;
  equipment: Record<string, Record<string, unknown>>; faults: Record<string, Record<string, unknown>>;
  events: Event[]; series: { time_s: number; values: Record<string, Scalar> }[];
  scenario: { id: string | null; state: string; completed_steps: number; total_steps: number; assertions: Record<string, unknown>[] };
  error: string | null; write_count: number; lag_ms: number; model_warnings: string[];
  result: RunResult;
};
export type ProjectSummary = { id: string; name: string; updated_at?: string };
export type RunSummary = { id?: string; run_id?: string; project_name?: string; started_at?: string; status?: string; verdict?: string };
export type Tab = 'pid' | 'tags' | 'scenarios' | 'trends' | 'connection';

export const STATUS_LABELS: Record<Snapshot['status'], string> = { idle: 'Prêt', running: 'En cours', paused: 'En pause', stopped: 'Arrêté', error: 'Erreur' };
export const fmt = (value: unknown, digits = 1): string => typeof value === 'boolean' ? (value ? 'TRUE' : 'FALSE') : typeof value === 'number' ? value.toLocaleString('fr-CH', { maximumFractionDigits: digits }) : value == null ? '—' : String(value);
export const uid = (prefix: string): string => `${prefix.slice(0, 68)}_${crypto.randomUUID().slice(0, 8)}`;
