import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, FolderOpen, LoaderCircle, Search } from 'lucide-react';
import { api } from './api';
import type { Project, Tag } from './types';
import './tag-workflow.css';

export type DiscoveredNode = { node_id: string; name: string; kind: 'object' | 'variable'; data_type: string | null; readable: boolean; writable: boolean; selectable: boolean; reason: string };
type BrowseResult = { node_id: string; nodes: DiscoveredNode[]; offset: number; more: boolean; limit: number; namespace_index: number | null };
type Props = { project: Project; tag?: Tag; disabled: boolean; onSelect?: (node: DiscoveredNode) => void; onClose: () => void };

/** Metadata only: each explicit page request uses the existing server-side target policy. */
export function OpcUaBrowser({ project, tag, disabled, onSelect, onClose }: Props) {
  const [base] = useState(project);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [result, setResult] = useState<BrowseResult | null>(null);
  const [path, setPath] = useState([{ node_id: 'i=85', name: 'Objets du serveur' }]);
  const sequence = useRef(0);
  const frozen = disabled || project !== base;
  useEffect(() => () => { sequence.current++; }, []);
  const target = `${base.plc.approved_virtual_target} @ ${base.plc.endpoint}`;
  const browse = async (nextPath = path, offset = 0) => {
    if (frozen || busy) return;
    const ticket = ++sequence.current;
    setBusy(true); setError('');
    try {
      const data = await api<BrowseResult>('/opcua/browse', 'POST', { project: base, node_id: nextPath.at(-1)!.node_id, offset, confirmation: target });
      if (ticket !== sequence.current) return;
      setConfirmed(true); setResult(data); setPath(nextPath); setSearch('');
    } catch (error) {
      if (ticket === sequence.current) { setError(error instanceof Error ? error.message : String(error)); setConfirmed(false); setResult(null); }
    } finally { if (ticket === sequence.current) setBusy(false); }
  };
  const entries = result?.nodes.filter(node => `${node.name} ${node.node_id}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())) ?? [];
  return <section className="opcua-browser" aria-label="Explorateur OPC UA en lecture seule">
    <div className="section-heading"><div><h3>{tag ? `Choisir le NodeId de ${tag.name}` : 'Explorer les variables OPC UA'}</h3><p className="mono">{target}</p></div><button className="button" onClick={onClose}>Fermer l’explorateur</button></div>
    <p>Lecture des noms, types et droits sur la cible autorisée du poste. Cette exploration n’écrit aucune valeur et ne démarre aucun essai.</p>
    {tag && <p className="small-muted">Tag attendu : {tag.data_type} · {tag.direction === 'input' ? 'entrée simulée, accès serveur en écriture requis' : 'commande PLC, accès serveur en lecture requis'}.</p>}
    {frozen && <p className="inline-error" role="alert">La configuration ou l’état du projet a changé. Fermez l’explorateur et relisez le projet avant de continuer.</p>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    {!confirmed && <button className="button primary" disabled={frozen || busy || base.plc.mode !== 'opcua'} onClick={() => void browse([{ node_id: 'i=85', name: 'Objets du serveur' }])}>{busy ? <LoaderCircle className="spin" size={16} /> : <Search size={16} />}Parcourir en lecture seule</button>}
    {confirmed && result && <>
      <div className="opcua-browser-toolbar"><button className="button" disabled={frozen || busy || path.length < 2} onClick={() => void browse(path.slice(0, -1))}><ArrowLeft size={15} />Dossier parent</button><span>{path.map(node => node.name).join(' / ')}</span><button className="button" disabled={frozen || busy} onClick={() => void browse(path, result.offset)}>Actualiser ce dossier</button></div>
      <label className="binding-search"><Search size={15} /><input aria-label="Filtrer les nœuds de cette page" value={search} onChange={event => setSearch(event.target.value)} placeholder="Filtrer les noms et NodeIds de cette page…" /></label>
      {busy && <p role="status">Lecture des métadonnées…</p>}
      <div className="opcua-node-list">{entries.map(node => {
        const mismatch = tag && (node.data_type !== tag.data_type || (tag.direction === 'input' ? !node.writable : !node.readable));
        const selectable = Boolean(onSelect && tag && node.selectable && !mismatch);
        return <div className="opcua-node" key={node.node_id}><div><strong>{node.name}</strong><code>{node.node_id}</code><small>{node.data_type ?? (node.kind === 'object' ? 'Dossier' : 'Type non pris en charge')}{node.reason ? ` · ${node.reason}` : ''}{mismatch ? ' · Incompatible avec ce tag' : ''}</small></div>{node.kind === 'object' ? <button className="button" disabled={frozen || busy || Boolean(node.reason)} onClick={() => void browse([...path, { node_id: node.node_id, name: node.name }])}><FolderOpen size={15} />Ouvrir {node.name}</button> : onSelect && <button className="button" disabled={frozen || busy || !selectable} onClick={() => { if (selectable && !frozen) onSelect(node); }}>Utiliser {node.name}</button>}</div>;
      })}{!entries.length && <p>{search ? 'Aucun nœud de cette page ne correspond au filtre.' : 'Ce dossier ne contient aucun nœud affichable.'}</p>}</div>
      <div className="opcua-pagination"><button className="button" disabled={frozen || busy || result.offset === 0} onClick={() => void browse(path, Math.max(0, result.offset - result.limit))}>Page précédente</button><span>Page {Math.floor(result.offset / result.limit) + 1} · {result.nodes.length} nœuds</span><button className="button" disabled={frozen || busy || !result.more || result.offset >= 1900} onClick={() => void browse(path, result.offset + result.limit)}>Page suivante</button></div>
      {result.more && result.offset >= 1900 && <p className="small-muted">Exploration limitée à 2 000 nœuds par dossier. Choisissez un sous-dossier ou utilisez un NodeId déjà découvert.</p>}
    </>}
  </section>;
}
