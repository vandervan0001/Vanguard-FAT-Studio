import { useId, useState, type ReactNode } from 'react';
import { LockKeyhole, Radio } from 'lucide-react';
import type { Snapshot } from './types';

export function ioBlockReason(state: Snapshot | null, unavailable?: string, allowPaused = false): string | undefined {
  if (unavailable) return unavailable;
  if (!state) return 'Attendez la connexion au service local.';
  if (state.status === 'error') return 'L’essai est en erreur. Consultez le diagnostic dans Connexion.';
  if (state.scenario.state === 'completed') return 'Le scénario est terminé. Arrêtez l’essai avant d’en démarrer un autre.';
  if (state.guided_steps?.at(-1)?.state === 'queued') return 'Le STEP est en cours d’application. Attendez la confirmation du cycle.';
  if (state.status === 'paused' && !allowPaused) return 'Cliquez sur « Reprendre » pour actionner cette entrée.';
  if (!state.run_id || !['running', 'paused'].includes(state.status)) return 'Démarrez l’essai pour modifier les entrées.';
}

export const READ_ONLY_IO = 'Cette variable est en lecture seule.';

function BlockedHint({ target, reason }: { target: string; reason: string }) {
  const [visible, setVisible] = useState(false);
  const id = useId();
  return <>
    <button
      type="button"
      className="io-help-hit"
      aria-label={`Afficher l’aide pour ${target}`}
      aria-expanded={visible}
      aria-describedby={visible ? id : undefined}
      title={reason}
      onClick={() => setVisible(!visible)}
    />
    {visible && <div id={id} className="io-block-feedback" role="status"><LockKeyhole size={13} />{reason}</div>}
  </>;
}

// Keep the actual controls natively disabled. A separate target can explain
// why a pointer or keyboard attempt cannot send a command.
export function IoControl({ target, reason, children }: { target: string; reason?: string; children: ReactNode }) {
  return <div className="io-control-target">
    {children}
    {reason && <BlockedHint key={reason} target={target} reason={reason} />}
  </div>;
}

export function IoPanelStatus({ reason, children }: { reason?: string; children: ReactNode }) {
  return <div className={`io-panel-status ${reason ? 'io-panel-blocked' : 'io-panel-active'}`}>
    <strong>{reason ? <LockKeyhole size={13} /> : <Radio size={13} />}{reason ? 'Commandes verrouillées' : 'Commandes disponibles'}</strong>
    <div>{reason ?? children}</div>
  </div>;
}
