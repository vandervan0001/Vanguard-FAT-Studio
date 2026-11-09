import { useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, Search, WandSparkles, X } from 'lucide-react';
import { useModalKeyboard } from './useModalKeyboard';
import { bindingOwners, compatibleTag, missingPortTags, suggestBindings } from './pidBuilder';
import { OpcUaBrowser } from './OpcUaBrowser';
import type { CatalogItem, Equipment, Project } from './types';
import './tag-workflow.css';

type Props = { project: Project; catalog: CatalogItem[]; locked: boolean; onChange: (update: (project: Project) => Project) => void; onClose: () => void };
function equipmentReference(equipment: Equipment) {
  const match = equipment.name.match(/^\s*([a-z]+)[\s_-]*(\d+)\b/i);
  return match ? (match[1] + match[2]).toLowerCase() : '';
}

export function GlobalBindings({ project, catalog, locked, onChange, onClose }: Props) {
  const [base] = useState(project);
  const [draft, setDraft] = useState(project);
  const [equipmentId, setEquipmentId] = useState(project.equipment[0]?.id ?? '');
  const [port, setPort] = useState('');
  const [search, setSearch] = useState('');
  const [notice, setNotice] = useState('');
  const [browsing, setBrowsing] = useState(false);
  useModalKeyboard(true, () => browsing ? setBrowsing(false) : onClose());
  const stale = project !== base;
  const disabled = locked || stale;
  const equipment = draft.equipment.find(entry => entry.id === equipmentId);
  const item = catalog.find(entry => entry.type === equipment?.type);
  const activePort = item && Object.hasOwn(item.ports, port) ? port : Object.keys(item?.ports ?? {})[0];
  const role = item?.ports[activePort];
  const selected = draft.tags.find(tag => tag.id === equipment?.bindings[activePort]);
  const allRoles = draft.equipment.flatMap(entry => Object.entries(catalog.find(spec => spec.type === entry.type)?.ports ?? {}).map(([key, spec]) => ({ entry, key, spec, tag: draft.tags.find(tag => tag.id === entry.bindings[key]) })));
  const validRole = ({ entry, key, spec, tag }: typeof allRoles[number]) => Boolean(tag && compatibleTag(tag, spec) && !bindingOwners(draft, entry, entry.bindings, key, catalog, tag.id).length);
  const required = allRoles.filter(entry => entry.spec.required);
  const missing = required.filter(entry => !validRole(entry));
  const problems = allRoles.filter(entry => entry.entry.bindings[entry.key] && !validRole(entry));
  const candidates = role ? draft.tags.filter(tag => compatibleTag(tag, role) && `${tag.name} ${tag.id} ${tag.plc_symbol ?? ''} ${tag.node_id}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())) : [];
  const changed = JSON.stringify(draft) !== JSON.stringify(base);
  const updateEquipment = (transform: (entry: Equipment) => Equipment) => setDraft(current => ({ ...current, equipment: current.equipment.map(entry => entry.id === equipmentId ? transform(entry) : entry) }));
  const choose = (tagId: string) => updateEquipment(entry => {
    const bindings = { ...entry.bindings };
    if (tagId) bindings[activePort] = tagId; else delete bindings[activePort];
    return { ...entry, bindings };
  });
  const propose = () => {
    if (disabled) return;
    let proposed = draft;
    let count = 0;
    const ambiguous: string[] = [];
    for (const entry of draft.equipment) {
      const reference = equipmentReference(entry);
      if (reference && draft.equipment.filter(other => equipmentReference(other) === reference).length > 1) { ambiguous.push(entry.name); continue; }
      const spec = catalog.find(item => item.type === entry.type);
      if (!spec) continue;
      const bindings = suggestBindings(proposed, entry, spec, catalog, entry.bindings);
      count += Object.keys(bindings).length - Object.keys(entry.bindings).length;
      proposed = { ...proposed, equipment: proposed.equipment.map(item => item.id === entry.id ? { ...entry, bindings } : item) };
    }
    setDraft(proposed);
    setNotice(`${count} association(s) proposée(s). Les correspondances ambiguës restent à choisir.${ambiguous.length ? ` Repères d’équipements répétés : ${[...new Set(ambiguous)].join(', ')}.` : ''}`);
  };
  return createPortal(<div className="modal-backdrop"><section className="modal global-binding-modal" role="dialog" aria-modal="true" aria-labelledby="global-bindings-title">
    <div className="modal-heading"><div><div className="eyebrow">TOUS LES ÉQUIPEMENTS</div><h2 id="global-bindings-title">Revoir les liaisons aux tags</h2></div><button className="icon-button" aria-label="Fermer la revue des liaisons" onClick={onClose}><X size={18} /></button></div>
    <p>Choisissez l’équipement, son rôle et le tag compatible. Les changements restent dans cette revue jusqu’à leur application au brouillon.</p>
    <div className="global-binding-summary" aria-live="polite"><strong>{required.length - missing.length} / {required.length} rôles requis associés</strong><span>{allRoles.filter(validRole).length} / {allRoles.length} rôles au total</span><span>{missing.length} requis à compléter</span></div>
    {disabled && <p className="inline-error" role="alert">{stale ? 'Le projet a changé. La sélection reste visible ; fermez et relisez le projet avant de recommencer.' : 'Le projet est verrouillé. La sélection reste conservée dans cette fenêtre.'}</p>}
    {notice && <p role="status" className="binding-notice">{notice}</p>}
    {browsing && selected ? <OpcUaBrowser project={draft} tag={selected} disabled={disabled} onClose={() => setBrowsing(false)} onSelect={node => {
      setDraft(current => ({ ...current, tags: current.tags.map(tag => tag.id === selected.id ? { ...tag, node_id: node.node_id } : tag) })); setBrowsing(false);
    }} /> : <>
      <div className="button-row"><button className="button" disabled={disabled || !draft.equipment.length} onClick={propose}><WandSparkles size={15} />Proposer pour tous les équipements</button></div>
      <div className="global-binding-grid">
        <nav className="binding-roles" aria-label="Équipements à associer">{draft.equipment.map(entry => {
          const roles = required.filter(role => role.entry.id === entry.id);
          return <button key={entry.id} className={entry.id === equipmentId ? 'active' : ''} aria-pressed={entry.id === equipmentId} onClick={() => { setEquipmentId(entry.id); setPort(''); setSearch(''); }}><strong>{entry.name}</strong><small>{roles.filter(validRole).length} / {roles.length} requis</small>{draft.equipment.some(other => other.id !== entry.id && equipmentReference(other) === equipmentReference(entry)) && <small>{entry.id}</small>}</button>;
        })}</nav>
        <nav className="binding-roles" aria-label="Rôles à associer">{item && Object.entries(item.ports).map(([key, spec]) => {
          const tag = draft.tags.find(tag => tag.id === equipment?.bindings[key]);
          return <button key={key} className={key === activePort ? 'active' : ''} aria-pressed={key === activePort} onClick={() => { setPort(key); setSearch(''); }}><span>{spec.label}{spec.required ? ' · requis' : ''}</span><small>{tag?.name ?? 'À associer'}</small></button>;
        })}</nav>
        <div className="binding-picker">{role && equipment && item ? <>
          <h3>{equipment.name} · {role.label}</h3><p className="small-muted">{role.direction === 'input' ? 'Entrée simulée vers l’automate' : 'Commande lue depuis l’automate'} · {role.data_types.join(' / ')}</p>
          <label className="binding-search"><Search size={15} /><input aria-label="Filtrer les tags de la revue" value={search} onChange={event => setSearch(event.target.value)} placeholder="Nom, repère ou symbole…" /></label>
          <div className="binding-candidates"><button disabled={disabled} className={!selected ? 'selected' : ''} onClick={() => choose('')}>Non associé</button>{candidates.map(tag => {
            const owners = bindingOwners(draft, equipment, equipment.bindings, activePort, catalog, tag.id);
            return <button key={tag.id} disabled={disabled || Boolean(owners.length)} className={selected?.id === tag.id ? 'selected' : ''} onClick={() => choose(tag.id)}><strong>{tag.name}</strong><small>{tag.id} · {tag.data_type}{owners.length ? ` · Déjà produit par ${owners.join(', ')}` : ''}</small>{selected?.id === tag.id && <Check size={14} />}</button>;
          })}{!candidates.length && <p>Aucun tag compatible avec ce filtre.</p>}</div>
          <button className="button" disabled={disabled || !Object.keys(item.ports).some(key => !equipment.bindings[key])} onClick={() => {
            const additions = missingPortTags(equipment, item);
            if (draft.tags.length + additions.tags.length > 200) { setNotice('Le projet est limité à 200 tags.'); return; }
            setDraft(current => ({ ...current, tags: [...current.tags, ...additions.tags], equipment: current.equipment.map(entry => entry.id === equipment.id ? { ...entry, bindings: additions.bindings } : entry) }));
            setNotice(`${additions.tags.length} tag(s) local(aux) préparé(s) pour ${equipment.name}, sans NodeId.`);
          }}>Créer les tags manquants de cet équipement</button>
          {selected && <div className="global-nodeid"><label>NodeId OPC UA de {selected.name}<input disabled={disabled} value={selected.node_id} onChange={event => setDraft(current => ({ ...current, tags: current.tags.map(tag => tag.id === selected.id ? { ...tag, node_id: event.target.value } : tag) }))} /></label>{draft.plc.mode === 'opcua' && <button className="button" disabled={disabled} onClick={() => setBrowsing(true)}>Choisir sur le serveur OPC UA</button>}<small>La démo utilise des tags locaux. Aucun NodeId ni aucune échelle n’est déduit du repère.</small></div>}
        </> : <p>Ajoutez un équipement au P&ID pour associer ses tags.</p>}</div>
      </div>
    </>}
    {problems.length > 0 && <div className="inline-error" role="alert"><p>{problems.length} association(s) existante(s) incompatible(s) ou déjà produite(s). Ouvrez le rôle à corriger.</p>{problems.map(problem => <button key={`${problem.entry.id}:${problem.key}`} className="button" onClick={() => { setEquipmentId(problem.entry.id); setPort(problem.key); setSearch(''); setBrowsing(false); }}>{problem.entry.name} · {problem.spec.label}</button>)}</div>}
    <div className="modal-actions"><button className="button" onClick={onClose}>Annuler</button><button className="button primary" disabled={disabled || !changed || Boolean(problems.length) || browsing} onClick={() => { if (!disabled) { onChange(current => current === base ? draft : current); onClose(); } }}>Appliquer les liaisons au brouillon</button></div>
  </section></div>, document.body);
}
