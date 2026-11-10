import { useEffect, useRef, useState } from 'react';
import { api } from './api';
import type { Project } from './types';
import './target-picker.css';

type KnownTarget = { id: string; name: string; endpoint: string; expected_application_uri: string; approved_virtual_target: string; server_certificate_sha256: string; security_policy: Project['plc']['security_policy']; authentication_required: boolean; selectable: boolean; reason: string };
type Preview = { project: Project; target: KnownTarget; authentication_required: boolean; notice: string };
type Check = { connected: boolean; identity_verified: boolean; mapping_checked: boolean; target: string; message: string };
type Props = { project: Project; locked: boolean; onChange: (update: (project: Project) => Project) => void };

export function TargetPicker({ project, locked, onChange }: Props) {
  const [targets, setTargets] = useState<KnownTarget[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [preview, setPreview] = useState<{ base: Project; value: Preview } | null>(null);
  const [check, setCheck] = useState<{ base: Project; value: Check } | null>(null);
  const current = useRef(project);
  const sequence = useRef(0);
  const pending = useRef<AbortController | null>(null);
  current.current = project;
  const chosen = targets.find(target => target.id === selectedId);
  const stale = Boolean(preview && preview.base !== project);

  async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const controller = new AbortController();
    pending.current?.abort(); pending.current = controller;
    const timeout = setTimeout(() => controller.abort(), path === '/connection/check' ? 25000 : 8000);
    try { return await api<T>(path, method, body, controller.signal); }
    catch (cause) {
      if (controller.signal.aborted) throw new Error('Le service local n’a pas répondu à temps. Vérifiez sa disponibilité puis réessayez.');
      throw cause;
    } finally { clearTimeout(timeout); if (pending.current === controller) pending.current = null; }
  }

  const refresh = async () => {
    const ticket = ++sequence.current;
    setLoading(true); setError(''); setSelectedId(''); setPreview(null);
    try {
      const data = await request<{ targets: KnownTarget[] }>('/connection/targets');
      if (sequence.current === ticket) setTargets(data.targets);
    } catch (cause) { if (sequence.current === ticket) setError(String(cause instanceof Error ? cause.message : cause)); }
    finally { if (sequence.current === ticket) setLoading(false); }
  };
  useEffect(() => { void refresh(); return () => { sequence.current++; pending.current?.abort(); }; }, []);
  useEffect(() => { setCheck(null); }, [project]);

  const prepare = async () => {
    if (locked || busy || !chosen?.selectable) return;
    const base = project, ticket = ++sequence.current;
    setBusy(true); setError(''); setNotice(''); setPreview(null);
    try {
      const value = await request<Preview>('/connection/targets/preview', 'POST', { project: base, target_id: chosen.id });
      if (sequence.current === ticket) setPreview({ base, value });
    } catch (cause) { if (sequence.current === ticket) setError(String(cause instanceof Error ? cause.message : cause)); }
    finally { if (sequence.current === ticket) setBusy(false); }
  };
  const verify = async () => {
    if (locked || busy || project.plc.mode !== 'opcua') return;
    const base = project, ticket = ++sequence.current;
    setBusy(true); setError(''); setCheck(null);
    try {
      const value = await request<Check>('/connection/check', 'POST', { project: base, confirmation: `${base.plc.approved_virtual_target} @ ${base.plc.endpoint}` });
      if (sequence.current === ticket && current.current === base) setCheck({ base, value });
    } catch (cause) { if (sequence.current === ticket) setError(String(cause instanceof Error ? cause.message : cause)); }
    finally { if (sequence.current === ticket) setBusy(false); }
  };

  return <section className="target-picker" aria-label="Cibles habituelles">
    <div className="target-picker-heading"><div><h3>Mes cibles sur ce poste</h3><p>Reprendre une identité déjà autorisée dans la politique locale.</p></div><button className="button" disabled={loading || busy} onClick={() => void refresh()}>Actualiser les cibles</button></div>
    {loading && <p role="status">Lecture des autorisations du poste…</p>}
    {!loading && !targets.length && <p className="small-muted">Aucune cible enregistrée sur ce poste. Utilisez la commande locale <code>fat-studio authorize-target</code> après vérification de votre adaptateur virtuel isolé. La démo reste disponible sans automate.</p>}
    {targets.length > 0 && <><label>Cible habituelle<select aria-label="Cible habituelle" disabled={locked || loading || busy} value={selectedId} onChange={event => { setSelectedId(event.target.value); setPreview(null); setNotice(''); setError(''); }}><option value="">Choisir une cible…</option>{targets.map(target => <option key={target.id} value={target.id}>{target.name} · {target.endpoint}</option>)}</select></label>
      {chosen && <div className="target-identity"><dl><dt>Adresse</dt><dd>{chosen.endpoint}</dd><dt>Identité serveur</dt><dd>{chosen.expected_application_uri}</dd><dt>Sécurité proposée</dt><dd>{chosen.security_policy === 'None' ? 'None · réseau virtuel isolé, sans chiffrement' : 'Basic256Sha256 · SignAndEncrypt'}</dd>{chosen.server_certificate_sha256 && <><dt>Empreinte serveur</dt><dd>{chosen.server_certificate_sha256}</dd></>}</dl>{chosen.reason && <p className="inline-error">{chosen.reason}</p>}<button className="button" disabled={locked || loading || busy || !chosen.selectable} onClick={() => void prepare()}>Préparer cette cible</button></div>}
    </>}
    {preview && <div className="target-preview" aria-label="Aperçu de la cible"><strong>{preview.value.target.name}</strong><p>{preview.value.notice}</p><p>Le namespace de l’ancienne cible et ses références d’authentification sont effacés lors d’un changement d’identité. Les références déjà exactes pour cette cible sont conservées.</p>{preview.value.authentication_required && <p className="binding-notice">Complétez les références de certificat ou de variables d’environnement dans « Certificats et authentification », conformément à la politique du poste. La liste ne transmet aucun secret ni chemin de clé.</p>}{stale && <p className="inline-error" role="alert">Le projet a changé. Préparez à nouveau cette cible avant de l’appliquer.</p>}<div className="button-row"><button className="button" disabled={busy} onClick={() => setPreview(null)}>Annuler le choix</button><button className="button primary" disabled={locked || busy || stale} onClick={() => { if (locked || stale) return; const selected = preview; onChange(value => value === selected.base ? selected.value.project : value); setPreview(null); setNotice('Cible ajoutée au brouillon. Vérifiez la connexion, puis enregistrez le projet.'); }}>Utiliser cette cible dans le brouillon</button></div></div>}
    {notice && <p className="binding-notice" role="status">{notice}</p>}
    <div className="target-check"><button className="button" disabled={locked || busy || Boolean(preview) || project.plc.mode !== 'opcua' || !project.plc.expected_application_uri || !project.plc.approved_virtual_target} onClick={() => void verify()}>Vérifier la connexion en lecture seule</button><p>Vérifie l’identité de la cible affichée sans lire de valeurs de procédé, sans écrire et sans démarrer d’essai. Le mapping reste à vérifier.</p></div>
    {busy && <p role="status">Vérification en cours…</p>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    {check?.base === project && <p className="binding-notice" role="status">{check.value.message}</p>}
  </section>;
}
