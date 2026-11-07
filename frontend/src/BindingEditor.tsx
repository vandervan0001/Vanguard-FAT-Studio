import { useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, Plus, Search, WandSparkles, X } from 'lucide-react';
import { useModalKeyboard } from './useModalKeyboard';
import { bindingOwners, compatibleTag, makePortTag, missingPortTags, suggestBindings } from './pidBuilder';
import type { CatalogItem, Equipment, Project, Tag } from './types';

type Props = { project: Project; equipment: Equipment; item: CatalogItem; catalog: CatalogItem[]; locked: boolean;
  onChange: (update: (project: Project) => Project) => void; onClose: () => void };

export function BindingEditor({ project, equipment, item, catalog, locked, onChange, onClose }: Props) {
  const [base] = useState(project);
  const [bindings, setBindings] = useState({ ...equipment.bindings });
  const [created, setCreated] = useState<Tag[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [activePort, setActivePort] = useState(Object.keys(item.ports)[0]);
  const [search, setSearch] = useState('');
  const [newType, setNewType] = useState<Tag['data_type']>(item.ports[activePort]?.data_types[0] as Tag['data_type']);
  const [notice, setNotice] = useState('');
  useModalKeyboard(true, onClose);
  const stale = project !== base;
  const disabled = locked || stale;
  const tags = [...base.tags, ...created];
  const draft = { ...base, tags };
  const spec = item.ports[activePort];
  const selected = tags.find(tag => tag.id === bindings[activePort]);
  const missing = Object.entries(item.ports).filter(([port, spec]) => spec.required && !bindings[port]).length;
  const problems = Object.entries(item.ports).flatMap(([port, spec]) => {
    const tag = tags.find(tag => tag.id === bindings[port]);
    if (!bindings[port]) return [];
    if (!tag || !compatibleTag(tag, spec)) return [`${spec.label} : tag incompatible ou absent.`];
    const owners = bindingOwners(draft, equipment, bindings, port, catalog, tag.id);
    return owners.length ? [`${spec.label} : cette entrée est déjà produite par ${owners.join(', ')}.`] : [];
  });
  const candidates = tags.filter(tag => compatibleTag(tag, spec) && `${tag.name} ${tag.id} ${tag.plc_symbol ?? ''} ${tag.plc_address ?? ''} ${tag.node_id}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()));
  const changed = JSON.stringify(bindings) !== JSON.stringify(equipment.bindings) || created.length > 0 || Object.entries(mapping).some(([id, value]) => tags.find(tag => tag.id === id)?.node_id !== value);
  const choose = (id: string) => setBindings(current => { const next = { ...current }; if (id) next[activePort] = id; else delete next[activePort]; return next; });
  const activate = (port: string) => { setActivePort(port); setSearch(''); setNewType(item.ports[port].data_types[0] as Tag['data_type']); };
  const createMissing = () => {
    if (disabled) return;
    const result = missingPortTags({ ...equipment, bindings }, item);
    if (tags.length + result.tags.length > 200) { setNotice('Le projet est limité à 200 tags. Créez seulement les rôles utiles.'); return; }
    setCreated(current => [...current, ...result.tags]); setBindings(result.bindings);
    setNotice(`${result.tags.length} tag(s) préparé(s), sans NodeId OPC UA. Vous pouvez les renommer dans Variables & mapping.`);
  };
  return createPortal(<div className="modal-backdrop"><section className="modal binding-modal" role="dialog" aria-modal="true" aria-labelledby="binding-editor-title" aria-describedby="binding-editor-help">
    <div className="modal-heading"><div><div className="eyebrow">{equipment.name} · {item.label}</div><h2 id="binding-editor-title">Lier les tags automate</h2></div><button className="icon-button" aria-label="Fermer la liaison des tags" onClick={onClose}><X size={18} /></button></div>
    <p id="binding-editor-help">Choisissez un rôle, puis un tag compatible. Les propositions restent à relire avant application au brouillon.</p>
    <div className="button-row binding-toolbar"><button className="button" disabled={disabled} onClick={() => {
      const next = suggestBindings(draft, equipment, item, catalog, bindings);
      const count = Object.keys(next).length - Object.keys(bindings).length; setBindings(next);
      setNotice(count ? `${count} association(s) proposée(s) depuis le repère ${equipment.name}. Relisez chaque rôle.` : 'Aucune correspondance unique supplémentaire. Recherchez et choisissez les tags ci-dessous.');
    }}><WandSparkles size={15} />Proposer depuis le repère</button><button className="button" disabled={disabled || !Object.keys(item.ports).some(port => !bindings[port])} onClick={createMissing}><Plus size={15} />Créer les tags manquants</button></div>
    {notice && <p className="binding-notice" role="status">{notice}</p>}
    {disabled && <p className="inline-error" role="alert">{stale ? 'Le projet a changé. Votre sélection est conservée ici ; fermez cette revue et relisez le projet avant de recommencer.' : 'Le projet est verrouillé. Votre sélection est conservée ; aucune association ne sera appliquée.'}</p>}
    <div className="binding-workspace">
      <nav className="binding-roles" aria-label="Rôles de l’équipement">{Object.entries(item.ports).map(([port, role]) => {
        const tag = tags.find(tag => tag.id === bindings[port]);
        return <button key={port} className={activePort === port ? 'active' : ''} aria-pressed={activePort === port} onClick={() => activate(port)}>
          <span>{role.label}{role.required && <em> · requis</em>}</span><small>{tag?.name ?? (bindings[port] ? 'Tag absent' : 'À associer')}</small>
          {tag && compatibleTag(tag, role) && <Check size={14} />}
        </button>;
      })}</nav>
      <div className="binding-picker" key={activePort}>
        <h3>{spec.label}</h3><p className="small-muted">{spec.direction === 'input' ? 'Entrée simulée → automate' : 'Commande lue depuis l’automate'} · {spec.data_types.join(' / ')}{spec.unit ? ` · ${spec.unit}` : ''}</p>
        <label className="binding-search"><Search size={16} /><input aria-label="Rechercher un tag compatible" placeholder="Nom, symbole, adresse ou NodeId…" value={search} onChange={event => setSearch(event.target.value)} /></label>
        <div className="binding-candidates" role="group" aria-label={`Tags pour ${spec.label}`}>
          <button className={!bindings[activePort] ? 'selected' : ''} disabled={disabled} onClick={() => choose('')}>Non associé{!spec.required && <small>Rôle facultatif</small>}</button>
          {candidates.map(tag => {
            const owners = bindingOwners(draft, equipment, bindings, activePort, catalog, tag.id);
            return <button key={tag.id} className={bindings[activePort] === tag.id ? 'selected' : ''} aria-pressed={bindings[activePort] === tag.id} disabled={disabled || owners.length > 0} onClick={() => choose(tag.id)}>
              <strong>{tag.name}</strong><span>{tag.data_type}{tag.unit ? ` · ${tag.unit}` : ''}</span>
              <small>{owners.length ? `Déjà produit par ${owners.join(', ')}` : tag.plc_symbol || tag.node_id || 'Tag local · NodeId non renseigné'}</small>
              {tags.some(other => other.id !== tag.id && other.name === tag.name) && <small>Identifiant : {tag.id}{tag.plc_address ? ` · ${tag.plc_address}` : ''}</small>}
            </button>;
          })}
          {!candidates.length && <p>Aucun tag compatible avec cette recherche. Modifiez le filtre ou créez un tag.</p>}
        </div>
        <div className="binding-create">{spec.data_types.length > 1 && <select aria-label="Type du nouveau tag" disabled={disabled} value={newType} onChange={event => setNewType(event.target.value as Tag['data_type'])}>{spec.data_types.map(type => <option key={type}>{type}</option>)}</select>}<button className="button" disabled={disabled || tags.length >= 200 || created.some(tag => tag.id === selected?.id && tag.data_type === newType)} onClick={() => {
          const tag = makePortTag(equipment, activePort, spec, newType); setCreated(current => [...current, tag]); choose(tag.id); setSearch('');
          setNotice(`Tag ${tag.name} préparé pour ce rôle. Le NodeId reste à renseigner pour une connexion OPC UA.`);
        }}><Plus size={14} />Créer un tag {newType}</button></div>
        {selected && <details className="binding-address"><summary>NodeId OPC UA de {selected.name}</summary><label>NodeId OPC UA<input aria-label="NodeId du tag sélectionné" disabled={disabled} value={mapping[selected.id] ?? selected.node_id} placeholder="Coller le NodeId découvert sur le serveur" onChange={event => setMapping(current => ({ ...current, [selected.id]: event.target.value }))} /></label><p className="small-muted">Inutile en démonstration. Utilisez l’identifiant fourni par le serveur ; une adresse Siemens ne permet pas de le déduire. Ce changement concerne toutes les utilisations de ce tag.</p></details>}
      </div>
    </div>
    {problems.length > 0 && <div className="inline-error" role="alert">{problems.map(problem => <p key={problem}>{problem}</p>)}</div>}
    <div className="modal-actions binding-actions"><span className="small-muted">{Object.keys(item.ports).filter(port => bindings[port]).length} / {Object.keys(item.ports).length} rôles associés{missing > 0 ? ` · ${missing} requis à compléter` : ''}</span><button className="button" onClick={onClose}>Annuler</button><button className="button primary" disabled={disabled || !changed || problems.length > 0} onClick={() => {
      if (disabled || problems.length) return;
      const used = new Set(Object.values(bindings));
      const additions = created.filter(tag => used.has(tag.id));
      onChange(current => current !== base ? current : { ...current, tags: [...current.tags, ...additions].map(tag => Object.hasOwn(mapping, tag.id) ? { ...tag, node_id: mapping[tag.id] } : tag), equipment: current.equipment.map(entry => entry.id === equipment.id ? { ...entry, bindings } : entry) });
      onClose();
    }}>Appliquer au brouillon</button></div>
  </section></div>, document.body);
}
