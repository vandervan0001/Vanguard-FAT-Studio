import { usePidConventions } from './pidConventions';

export default function PidConventionsGuide() {
  const { conventions, error } = usePidConventions();
  return <section className="pid-conventions-guide" aria-label="Conventions et références P&ID">
    <h3>Conventions et références P&ID</h3>
    <p>Les repères du document importé restent conservés. Les codes ci-dessous servent à préparer une convention de projet ; ils ne renomment aucun équipement.</p>
    {error && <p className="pid-blocked" role="status">Références indisponibles : {error}</p>}
    {!conventions && !error && <p className="small-muted">Chargement des conventions locales…</p>}
    {conventions && <>
      <p>{conventions.notice}</p>
      <details><summary>Services, codes et couleurs du projet</summary><p>Un service est choisi sur chaque liaison. Aucune température, fonction ni couleur source n’est déduite automatiquement.</p><ul className="pid-service-list">{conventions.services.map(service => <li key={service.id}><i aria-hidden="true" style={{ backgroundColor: service.color }} /><code>{service.code || '—'}</code><span>{service.label}</span></li>)}</ul></details>
      <details><summary>Repères usuels d’instrumentation</summary><div className="pid-conventions-table-wrap"><table><thead><tr><th>Code</th><th>Fonction</th><th>Exemple</th></tr></thead><tbody>{conventions.instruments.map(instrument => <tr key={instrument.code}><td><code>{instrument.code}</code></td><td>{instrument.label}</td><td><code>{instrument.example}</code></td></tr>)}</tbody></table></div></details>
      <details><summary>Sources et portée des références</summary><ul className="pid-reference-list">{conventions.references.map(reference => <li key={reference.id}><a href={/^https?:\/\//i.test(reference.url) ? reference.url : undefined} target="_blank" rel="noopener noreferrer">{reference.title}</a><p>{reference.scope}</p></li>)}</ul></details>
    </>}
  </section>;
}
