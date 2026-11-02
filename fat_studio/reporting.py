"""Standalone, escaped reports and streamed CSV evidence."""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json

from . import __version__
from .storage import Store, encode


def cell(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def csv_stream(store: Store, run_id: str, *, run: dict | None = None):
    # Capture eagerly, before StreamingResponse sends headers or changes thread.
    run = store.run(run_id) if run is None else run
    tags = {tag["id"]: tag for tag in run["project"]["tags"]}

    def stream():
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["run_id", "timestamp_utc", "sim_time_s", "tag_id", "tag_name", "direction", "data_type", "value", "unit", "quality"])
        yield "\ufeff" + output.getvalue()
        samples = store.samples(run_id, through_id=run["snapshot"]["last_sample_id"])
        try:
            for sample in samples:
                output.seek(0)
                output.truncate(0)
                for tag_id, value in sample["values"].items():
                    tag = tags[tag_id]
                    writer.writerow([run_id, sample["timestamp"], round(sample["sim_time_s"], 6), tag_id,
                                     cell(tag["name"]), tag["direction"], tag["data_type"], value,
                                     cell(tag["unit"]), sample["qualities"].get(tag_id, "unknown")])
                yield output.getvalue()
        finally:
            samples.close()
    return stream()


def json_stream(store: Store, run_id: str, *, run: dict | None = None):
    run = dict(store.run(run_id) if run is None else run)
    run["software_version"] = __version__
    run["project_sha256"] = hashlib.sha256(encode(run["project"]).encode()).hexdigest()

    def stream():
        yield encode(run)[:-1] + ',"samples":['
        samples = store.samples(run_id, through_id=run["snapshot"]["last_sample_id"])
        try:
            for index, sample in enumerate(samples):
                yield ("," if index else "") + encode(sample)
            yield "]}"
        finally:
            samples.close()
    return stream()


def html_report(store: Store, run_id: str, *, run: dict | None = None) -> str:
    run = store.run(run_id) if run is None else run
    def esc(value):
        return html.escape(str(value))
    project = run["project"]
    scenario = run["scenario"]
    assertions = [event for event in run["events"] if event["kind"].startswith("assertion_")]
    passed = sum(event["kind"] == "assertion_pass" for event in assertions)
    result = run["result"]
    verdict = {"pass": "ACCEPTÉ PAR L'UTILISATEUR", "fail": "REFUSÉ PAR L'UTILISATEUR", "not_evaluated": "NON ÉVALUÉ"}[result["verdict"]]
    checksum = hashlib.sha256(encode(project).encode()).hexdigest()
    tag_rows = "".join(
        f"<tr><td>{esc(tag['name'])}</td><td>{esc(tag['id'])}</td><td>{esc(tag['direction'])}</td>"
        f"<td>{esc(tag['data_type'])}</td><td>{esc(tag['unit'])}</td><td>{esc(tag['node_id'])}</td></tr>"
        for tag in project["tags"]
    )
    event_rows = "".join(
        f"<tr><td>{esc(event['timestamp'])}</td><td>{event['sim_time_s']:.3f}</td>"
        f"<td>{esc(event['kind'])}</td><td>{esc(event['message'])}<details><summary>Détails</summary>"
        f"<pre>{esc(json.dumps(event['details'], ensure_ascii=False, indent=2))}</pre></details></td></tr>"
        for event in run["events"]
    )
    assertion_rows = "".join(
        f"<tr><td>{esc(event['details'].get('target', ''))}</td>"
        f"<td>{esc(event['details'].get('operator', ''))} {esc(event['details'].get('expected', ''))}</td>"
        f"<td>{esc(event['details'].get('actual', ''))}</td><td>{event['sim_time_s']:.3f}</td>"
        f"<td>{'OK' if event['kind'] == 'assertion_pass' else 'ÉCHEC'}</td></tr>"
        for event in assertions
    )
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rapport FAT — {esc(project['name'])}</title><style>
:root{{font-family:system-ui,sans-serif;color:#182b3a;background:#eef2f5}}body{{max-width:1150px;margin:40px auto;padding:36px;background:white}}h1{{font-size:30px}}h2{{margin-top:36px;border-bottom:2px solid #dbe4eb;padding-bottom:8px}}.eyebrow{{font-size:12px;letter-spacing:2px;color:#436475}}.status{{padding:15px;background:#edf5fb;border-left:4px solid #0b6970;font-weight:bold}}dl{{display:grid;grid-template-columns:180px 1fr;gap:9px}}dt{{font-weight:600}}dd{{margin:0;overflow-wrap:anywhere}}table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{border:1px solid #dbe4eb;padding:8px;vertical-align:top;text-align:left;overflow-wrap:anywhere}}th{{background:#eff4f7}}pre{{font-size:11px;white-space:pre-wrap;overflow-wrap:anywhere}}.note{{padding:14px;background:#fff6e5;line-height:1.5}}@media print{{body{{margin:0;padding:10px}}details{{display:block}}h2{{break-after:avoid}}tr{{break-inside:avoid}}}}
</style></head><body><div class="eyebrow">FAT STUDIO · ESSAI FONCTIONNEL LOCAL</div>
<h1>{esc(project['name'])}</h1><div class="status">{verdict}</div>
<dl><dt>Identifiant</dt><dd>{esc(run_id)}</dd><dt>Version logiciel</dt><dd>{__version__}</dd>
<dt>Début UTC</dt><dd>{esc(run['started_at'])}</dd><dt>Fin UTC</dt><dd>{esc(run['ended_at'] or 'Essai encore ouvert')}</dd>
<dt>Instant de l'export UTC</dt><dd>{esc(run['snapshot']['captured_at'])}</dd>
<dt>Statut technique</dt><dd>{esc(run['status'])}</dd><dt>Mode / cible</dt><dd>{esc(project['plc']['mode'])} — {esc(run['connection']['target'])}</dd>
<dt>Scénario</dt><dd>{esc(scenario['name'] if scenario else 'Essai manuel')}</dd><dt>Pas / vitesse</dt><dd>{project['simulation']['step_ms']} ms / {project['simulation']['speed']}×</dd>
<dt>Échantillons</dt><dd>{run['sample_count']} cycles enregistrés</dd><dt>Assertions</dt><dd>{passed} réussies sur {len(assertions)} évaluées</dd>
<dt>Projet SHA-256</dt><dd>{checksum}</dd></dl>
<p class="note">Modèle simplifié de volume et de débits ; aucune validation de sécurité ni autorisation de mise en service.
Les assertions automatiques sont distinctes du verdict utilisateur. En OPC UA, les conditions initiales du PLC sont à rétablir manuellement avant chaque répétition ; le banc ne commande jamais RUN/STOP.</p>
<h2>Conclusion de l'utilisateur</h2><p>{esc(result['comment'] or 'Aucun commentaire renseigné.')}</p>
<h2>Assertions du scénario</h2><table><thead><tr><th>Variable</th><th>Attendu</th><th>Observé</th><th>Temps simulé s</th><th>Résultat</th></tr></thead><tbody>{assertion_rows}</tbody></table>
<h2>Variables suivies</h2><table><thead><tr><th>Nom</th><th>ID</th><th>Sens</th><th>Type</th><th>Unité</th><th>NodeId configuré</th></tr></thead><tbody>{tag_rows}</tbody></table>
<h2>Journal et défauts injectés</h2><table><thead><tr><th>UTC</th><th>Simulation s</th><th>Événement</th><th>Description</th></tr></thead><tbody>{event_rows}</tbody></table>
<h2>Configuration de référence</h2><details><summary>Projet et paramètres enregistrés au début de l'essai</summary><pre>{esc(json.dumps(project, ensure_ascii=False, indent=2))}</pre></details>
<h2>Scénario enregistré</h2><pre>{esc(json.dumps(scenario, ensure_ascii=False, indent=2))}</pre>
<p>Les valeurs détaillées et leur qualité sont disponibles dans l'export CSV ; l'export JSON contient l'ensemble des preuves. Ce rapport est généré localement, sans service externe.</p>
</body></html>"""
