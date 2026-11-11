import type { DrawingRevision, PidDrawingPreview, PidDrawingSettings } from './types';

export const drawingDefaults = (settings?: PidDrawingSettings): PidDrawingSettings => ({
  paper_size: 'A3', orientation: 'landscape', company: '', client: '', project_reference: '', site: '', unit: '',
  drawing_title: '', document_number: '', revision: '00', issue_date: '', drawn_by: '', checked_by: '', approved_by: '',
  status: 'draft', sheet_number: 1, sheet_total: 1, notes: '', revisions: [], show_legend: true, layout_style: 'compact', color_mode: 'service', ...settings,
  ...(settings?.revisions ? { revisions: settings.revisions.map(row => ({ ...row })) } : {}),
});

const dateValid = (date: string) => !date || /^\d{4}-\d{2}-\d{2}$/.test(date) && Number.isFinite(Date.parse(`${date}T00:00:00Z`)) && new Date(`${date}T00:00:00Z`).toISOString().slice(0, 10) === date;
export function drawingValidation(settings: PidDrawingSettings): string {
  if (![settings.sheet_number, settings.sheet_total].every(value => Number.isInteger(value) && value >= 1 && value <= 999) || settings.sheet_number > settings.sheet_total) return 'Le numéro du folio doit être compris entre 1 et le nombre total de folios (999 au maximum).';
  if (!dateValid(settings.issue_date) || settings.revisions.some(row => !dateValid(row.date))) return 'Renseignez une date valide ou laissez le champ vide.';
  if (settings.revisions.some(row => !row.revision.trim() || !row.description.trim())) return 'Chaque ligne d’historique demande un indice et une description. Retirez les lignes inutilisées.';
  return '';
}

type Props = {
  settings: PidDrawingSettings; projectName: string; busy: boolean; dirty: boolean; mismatch: boolean;
  actionBlocked: string; previewBlocked: string; validation: string;
  preview: PidDrawingPreview | null; previewStale: boolean;
  onChange: (settings: PidDrawingSettings) => void; onPreview: () => void; onApply: () => void; onSave: () => void;
  onReload: () => void; onDownload: () => void;
};
type TextField = 'company' | 'client' | 'project_reference' | 'site' | 'unit' | 'drawing_title' | 'document_number' | 'revision' | 'issue_date' | 'drawn_by' | 'checked_by' | 'approved_by';

export default function PidDrawingEditor({ settings, projectName, busy, dirty, mismatch, actionBlocked, previewBlocked, validation, preview, previewStale, onChange, onPreview, onApply, onSave, onReload, onDownload }: Props) {
  const update = <K extends keyof PidDrawingSettings>(key: K, value: PidDrawingSettings[K]) => onChange({ ...settings, [key]: value });
  const text = (key: TextField, label: string, maximum: number, type = 'text', placeholder?: string) => <label key={key}>{label}<input aria-label={label} type={type} maxLength={maximum} value={settings[key]} disabled={busy} placeholder={placeholder} onChange={event => update(key, event.target.value)} /></label>;
  const revise = (index: number, key: keyof DrawingRevision, value: string) => update('revisions', settings.revisions.map((row, rowIndex) => rowIndex === index ? { ...row, [key]: value } : row));
  return <section className="pid-drawing-editor" aria-label="Mise en page du P&ID">
    <div className="pid-drawing-heading"><h3>Mise en page du dessin</h3><p>Cartouche, format et historique du projet. Les champs laissés vides restent sans renseignement. Échelle de procédé : <strong>sans échelle</strong>.</p></div>
    {mismatch && <div className="pid-message" role="status"><p>Le contexte du projet a changé. Votre mise en page est conservée ; vérifiez le projet actif avant de reprendre ces réglages.</p></div>}
    {validation && <p className="pid-blocked" role="status">{validation}</p>}
    <div className="pid-drawing-grid"><div className="pid-drawing-fields">
      <fieldset><legend>Document</legend><div className="pid-drawing-form">
        {text('drawing_title', 'Titre du dessin', 160, 'text', projectName)}
        {text('document_number', 'Numéro du document', 64)}
        {text('revision', 'Indice de révision', 16)}
        {text('issue_date', 'Date d’émission', 10, 'date')}
        <label>Statut déclaré<select aria-label="Statut déclaré" disabled={busy} value={settings.status} onChange={event => update('status', event.target.value as PidDrawingSettings['status'])}><option value="draft">Brouillon</option><option value="for_review">Pour revue</option><option value="for_information">Pour information</option><option value="for_construction">Pour construction</option><option value="as_built">Tel que construit</option></select></label>
      </div></fieldset>
      <details className="pid-drawing-section"><summary>Entreprise et projet</summary><div className="pid-drawing-form">
        {text('company', 'Entreprise', 100)}{text('client', 'Client', 100)}{text('project_reference', 'Référence du projet', 64)}{text('site', 'Site', 100)}{text('unit', 'Unité / installation', 80)}
      </div></details>
      <details className="pid-drawing-section"><summary>Format et folio</summary><div className="pid-drawing-form">
        <label>Présentation du cartouche<select aria-label="Présentation du cartouche" value={settings.layout_style ?? 'compact'} disabled={busy} onChange={event => update('layout_style', event.target.value as PidDrawingSettings['layout_style'])}><option value="compact">Compact</option><option value="full">Détaillé</option></select></label>
        <label>Couleurs du dessin<select aria-label="Couleurs du dessin" value={settings.color_mode ?? 'service'} disabled={busy} onChange={event => update('color_mode', event.target.value as PidDrawingSettings['color_mode'])}><option value="service">Couleurs des services</option><option value="monochrome">Noir et blanc</option></select></label>
        <label>Format du papier<select aria-label="Format du papier" value={settings.paper_size} disabled={busy} onChange={event => update('paper_size', event.target.value as PidDrawingSettings['paper_size'])}>{['A4', 'A3', 'A2', 'A1', 'A0'].map(size => <option key={size} value={size}>{size}</option>)}</select></label>
        <label>Orientation<select aria-label="Orientation" value={settings.orientation} disabled={busy} onChange={event => update('orientation', event.target.value as PidDrawingSettings['orientation'])}><option value="landscape">Paysage</option><option value="portrait">Portrait</option></select></label>
        <label>Numéro du folio<input aria-label="Numéro du folio" type="number" min="1" max="999" step="1" value={settings.sheet_number} disabled={busy} onChange={event => update('sheet_number', Number(event.target.value))} /></label>
        <label>Nombre total de folios<input aria-label="Nombre total de folios" type="number" min="1" max="999" step="1" value={settings.sheet_total} disabled={busy} onChange={event => update('sheet_total', Number(event.target.value))} /></label>
      </div><p className="small-muted">Le cartouche compact affiche les champs renseignés et les révisions déclarées. Les couleurs de service suivent la convention du projet ; les codes restent lisibles en noir et blanc.</p><p className="small-muted">Un seul folio est exporté par fichier. Cette numérotation ne crée pas d’autres feuilles.</p><label className="check-label"><input type="checkbox" disabled={busy} checked={settings.show_legend} onChange={event => update('show_legend', event.target.checked)} />Afficher la légende</label></details>
      <details className="pid-drawing-section"><summary>Notes et mentions</summary><label>Notes du dessin<textarea aria-label="Notes du dessin" rows={5} maxLength={1200} disabled={busy} value={settings.notes} onChange={event => update('notes', event.target.value)} /></label><p className="small-muted">{settings.notes.length} / 1 200 caractères</p></details>
      <details className="pid-drawing-section"><summary>Visas déclarés</summary><p className="small-muted">Ces noms sont des mentions documentaires. Ils ne constituent ni signatures, ni validation FAT.</p><div className="pid-drawing-form">{text('drawn_by', 'Dessiné par', 64)}{text('checked_by', 'Vérifié par', 64)}{text('approved_by', 'Approuvé par', 64)}</div></details>
      <details className="pid-drawing-section"><summary>Historique des révisions ({settings.revisions.length} / 5)</summary>
        {settings.revisions.map((row, index) => <fieldset key={index} className="pid-revision-row"><legend>Révision {index + 1}</legend><div className="pid-drawing-form">
          <label>Indice<input aria-label={`Indice historique ${index + 1}`} maxLength={16} disabled={busy} value={row.revision} onChange={event => revise(index, 'revision', event.target.value)} /></label>
          <label>Date<input aria-label={`Date historique ${index + 1}`} type="date" disabled={busy} value={row.date} onChange={event => revise(index, 'date', event.target.value)} /></label>
          <label className="pid-drawing-wide">Description<input aria-label={`Description historique ${index + 1}`} maxLength={140} disabled={busy} value={row.description} onChange={event => revise(index, 'description', event.target.value)} /></label>
        </div><details className="pid-revision-staff"><summary>Visas de cette révision</summary><div className="pid-drawing-form">{(['drawn_by', 'checked_by', 'approved_by'] as const).map((key, staffIndex) => <label key={key}>{['Dessiné par', 'Vérifié par', 'Approuvé par'][staffIndex]}<input aria-label={`${['Dessiné par', 'Vérifié par', 'Approuvé par'][staffIndex]} historique ${index + 1}`} maxLength={64} disabled={busy} value={row[key]} onChange={event => revise(index, key, event.target.value)} /></label>)}</div></details><button className="button compact-button" disabled={busy} onClick={() => update('revisions', settings.revisions.filter((_, rowIndex) => rowIndex !== index))}>Retirer la révision {index + 1}</button></fieldset>)}
        <button className="button compact-button" disabled={busy || settings.revisions.length >= 5} onClick={() => update('revisions', [...settings.revisions, { revision: '', date: '', description: '', drawn_by: '', checked_by: '', approved_by: '' }])}>Ajouter une révision</button>
      </details>
    </div><aside className="pid-drawing-preview" aria-label="Aperçu de mise en page"><h4>Aperçu de la feuille</h4><p>Dessin enregistré, mise en page en préparation. Les modifications du graphe non enregistrées ne figurent pas dans cet aperçu.</p>
      <button className="button" disabled={busy || Boolean(validation || previewBlocked || mismatch)} onClick={onPreview}>{preview ? 'Actualiser l’aperçu' : 'Générer l’aperçu'}</button>
      {previewBlocked && <p className="small-muted">{previewBlocked}</p>}
      {preview && <><p className="pid-preview-size">{preview.width_mm} × {preview.height_mm} mm · sans échelle</p>{previewStale && <p className="pid-blocked">Réglages modifiés depuis cet aperçu.</p>}<img src={preview.image_data_url} alt="Aperçu de la feuille P&ID avec son cartouche" />{preview.warnings.length > 0 && <ul className="pid-preview-warnings">{preview.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>}</>}
      {!preview && <div className="pid-preview-empty">L’aperçu sera généré localement à partir du dessin enregistré.</div>}
    </aside></div>
    <div className="pid-drawing-actions"><p>{dirty ? 'Mise en page en préparation, conservée dans cet onglet.' : 'Réglages identiques au brouillon du projet.'}</p>{actionBlocked && <p className="pid-blocked">{actionBlocked}</p>}
      <div className="button-row"><button className="button" disabled={busy || Boolean(validation || actionBlocked || mismatch)} onClick={onApply}>Appliquer au projet</button><button className="button primary" disabled={busy || Boolean(validation || actionBlocked || mismatch)} onClick={onSave}>Enregistrer la mise en page</button></div>
      <div className="button-row pid-layout-recovery"><button className="button compact-button" disabled={busy} onClick={onDownload}>Télécharger le brouillon de mise en page</button><button className="button compact-button" disabled={busy} onClick={onReload}>Reprendre les réglages du projet actif</button></div>
    </div>
  </section>;
}
