"""Bounded local P&ID readers. Drawing/OCR results are reviewable hypotheses.

No parser supplies process parameters, PLC addresses, or human FAT conclusions.
SVG supports basic shapes, straight paths and affine transforms. DEXPI/Proteus
XML supports identified plant items, positions and explicit FromID/ToID links;
it is intentionally not a complete DEXPI schema implementation.
"""

from __future__ import annotations

import base64
import csv
import ctypes
import hashlib
import io
import json
import math
import re
import threading
import zipfile
import zlib
from collections import defaultdict, deque
from contextlib import closing
from pathlib import PurePosixPath

from pydantic import ValidationError

from .pid_models import PidConnection, PidDocument, PidEquipment, PidPage, PidPosition

MAX_UPLOAD = 20 * 1024 * 1024
MAX_ITEMS = 2000
MAX_SEGMENTS = 20000
MAX_XML_ELEMENTS = 100000
MAX_PIXELS = 30_000_000
MAX_DOCUMENT = 4 * 1024 * 1024
MAX_PREVIEWS = 2 * 1024 * 1024
_PDF_LOCK = threading.Lock()  # PDFium's native library is not thread safe.
_TAG = re.compile(r"(?<![\w-])(?:\d{1,5}[- ])?[A-Z]{1,6}[- ]?\d{1,6}[A-Z]?(?:[-.]\d{1,3})?(?![\w-])", re.I)
_NUMBER = r"[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?"
_PREFIX_TYPES = {"P": "pump", "PU": "pump", "PMP": "pump", "TK": "tank", "T": "tank",
                 "V": "valve", "XV": "valve_onoff", "CV": "valve_control", "FCV": "valve_control",
                 "LCV": "valve_control", "PCV": "valve_control", "TCV": "valve_control",
                 "HV": "manual_valve", "MOV": "valve_onoff", "SDV": "valve_onoff"}
_DOCUMENT_FIELD = re.compile(r"\b(?:FILE\s*NAME|(?:DRAWING|DWG|SHEET|PROJECT)\s*(?:NUMBER|NO\.?|#))\b", re.I)
_DOCUMENT_FILE = re.compile(r"\b[\w &().-]+\.(?:dwg|dxf|pdf|svg|png|jpe?g|tiff?)\b", re.I)
_DOCUMENT_REFERENCE = re.compile(r"\b(?:(?:REF(?:ERENCE)?|SEE)\s*(?:SHT|SHEET|DWG|DRAWING)|RE\s+SH[TL])\b", re.I)
_REGULATORY_TEXT = re.compile(r"\b(?:CFR|EPA|NPDES|ISO|IEC|REGULATION|REGULATORY|PERMIT)\b", re.I)


class _PdfGeometryLimit(Exception):
    """A bounded geometry scan is incomplete, so none of it may imply links."""


def _number(value) -> float:
    if isinstance(value, bool):
        raise ValueError("Valeur booléenne interdite dans une coordonnée numérique.")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("Coordonnée ou valeur numérique P&ID invalide.") from exc
    if not math.isfinite(result) or abs(result) > 100000:
        raise ValueError("Coordonnée ou valeur numérique non finie/hors limites dans le P&ID.")
    return result


def _text(value, maximum=200) -> str:
    return str(value or "").strip()[:maximum]


def _warn(doc, message):
    if message not in doc.warnings and len(doc.warnings) < 300:
        doc.warnings.append(message)


def _selection(pages: str, count: int, doc: PidDocument) -> list[int]:
    if count < 1 or count > 10000:
        raise ValueError("Nombre de pages hors limites (1 à 10 000).")
    if not pages.strip():
        if count > 1:
            _warn(doc, f"Le document contient {count} pages ; seule la première est importée. Choisir les pages pour en ajouter.")
        return [0]
    selected = set()
    if len(pages) > 200:
        raise ValueError("Sélection de pages trop longue.")
    for part in pages.split(","):
        match = re.fullmatch(r"\s*(\d{1,5})(?:\s*-\s*(\d{1,5}))?\s*", part)
        if not match:
            raise ValueError("Pages invalides : utiliser 1,3-5 (20 pages au maximum).")
        first, last = int(match[1]), int(match[2] or match[1])
        if first < 1 or last < first or last > count:
            raise ValueError(f"Page hors limites : le document contient {count} pages.")
        if last - first >= 20:
            raise ValueError("Sélection limitée à 20 pages.")
        selected.update(range(first - 1, last))
        if len(selected) > 20:
            raise ValueError("Sélection limitée à 20 pages.")
    return sorted(selected)


def _validate(doc: PidDocument) -> PidDocument:
    ids = [item.id for item in doc.equipment]
    if len(ids) != len(set(ids)):
        raise ValueError("Identifiants d'équipements dupliqués dans le P&ID.")
    edge_ids = [edge.id for edge in doc.connections]
    if len(edge_ids) != len(set(edge_ids)):
        raise ValueError("Identifiants de liaisons dupliqués dans le P&ID.")
    known = set(ids)
    if any(edge.source not in known or edge.target not in known for edge in doc.connections):
        raise ValueError("Une liaison référence un équipement absent du P&ID.")
    page_numbers = [page.number for page in doc.pages]
    if len(page_numbers) != len(set(page_numbers)):
        raise ValueError("Numéros de pages dupliqués dans le P&ID.")
    for page in doc.pages:
        if page.image_data_url and not page.image_data_url.startswith("data:image/png;base64,"):
            raise ValueError("L'aperçu P&ID doit être un PNG incorporé, sans ressource externe.")
        if page.image_data_url:
            try:
                preview = base64.b64decode(page.image_data_url.split(",", 1)[1], validate=True)
                if not preview.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("PNG attendu.")
                Image, _ = _pillow()
                with Image.open(io.BytesIO(preview)) as image:
                    if image.width * image.height > MAX_PIXELS:
                        raise ValueError("Dimensions d'aperçu PNG hors limites.")
            except (OSError, ValueError) as exc:
                raise ValueError("Aperçu PNG P&ID invalide.") from exc
    return doc


def _native(value) -> PidDocument:
    try:
        return _validate(PidDocument.model_validate(value))
    except ValidationError as exc:
        raise ValueError(f"Document fat-studio/pid invalide : {exc.errors()[0]['msg']}.") from exc


def _json(data):
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("JSON P&ID illisible ou trop imbriqué.") from exc
    stack = [(value, 0)]
    visited = 0
    while stack:
        item, depth = stack.pop()
        visited += 1
        if depth > 40 or visited > 200000:
            raise ValueError("JSON P&ID trop complexe.")
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    return value


def _id(raw, used):
    candidate = re.sub(r"[^A-Za-z0-9_-]", "_", str(raw))[:68] or "item"
    if not candidate[0].isalpha():
        candidate = "item_" + candidate
    base = candidate
    serial = 2
    while candidate in used:
        candidate = f"{base}_{serial}"
        serial += 1
    used.add(candidate)
    return candidate


def _kind(tag):
    prefix = re.sub(r"^\d+[- ]", "", tag.upper())
    prefix = re.match(r"[A-Z]+", prefix)
    prefix = prefix[0] if prefix else ""
    if prefix in _PREFIX_TYPES:
        return _PREFIX_TYPES[prefix]
    # AT can mean an analysis transmitter or a tank in a site's equipment legend.
    if prefix in {"FT", "FIT", "PT", "PIT", "LT", "LIT", "TT", "TIT", "AIT", "DT", "DIT"}:
        return "analog_sensor"
    if re.fullmatch(r"[FPLTAD]S[HL]{0,2}", prefix):
        return "digital_sensor"
    return "unknown"


def _explicit_kind(kind, node_type=""):
    from .pid_symbols import resolve_symbol

    symbol = resolve_symbol(kind)
    if symbol and symbol not in {"tank", "pump", "generic"}:
        return symbol
    key = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(kind)).lower().replace("-", "_").replace(" ", "_")
    if key in {"pump", "centrifugal_pump", "positive_displacement_pump", "metering_pump", "slurry_pump", "sump_pump"}:
        return "pump"
    if key in {"tank", "vessel", "pressure_vessel", "agitated_tank"}:
        return "tank"
    if key in {"control_valve", "pressure_regulator", "valve_control"}:
        return "valve_control"
    if key in {"on_off_valve", "solenoid_valve", "motor_operated_valve", "valve_onoff"}:
        return "valve_onoff"
    return _text(kind or node_type or "unknown", 80)


def _boolean(value):
    if not isinstance(value, bool):
        raise ValueError("Indicateur booléen JSON attendu (true ou false, sans guillemets).")
    return value


def _graph_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Valeur numérique JSON attendue pour une position, page ou confiance.")
    return _number(value)


def _confidence(value):
    result = _graph_number(value)
    if not 0 <= result <= 1:
        raise ValueError("Confiance P&ID hors limites (0 à 1).")
    return result


def _reference(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value):
        raise ValueError("Identifiant/référence du graphe invalide : chaîne ou entier attendu.")
    return str(value)


def _rotation(value):
    if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 90, 180, 270):
        raise ValueError("Rotation documentaire attendue : entier 0, 90, 180 ou 270 degrés.")
    return value


def _document_string(value, name):
    if not isinstance(value, str) or len(value) > 80:
        raise ValueError(f"{name} documentaire : chaîne de 80 caractères au maximum attendue.")
    return value


def _text_rotation(value):
    number = _number(value)
    if not number.is_integer():
        raise ValueError("Rotation documentaire entière attendue.")
    return _rotation(int(number))


def _text_attributes(attributes):
    """CSV/GraphML carry text: normalize declared scalar columns explicitly."""
    for name in ("x", "y", "page", "confidence"):
        if name in attributes and attributes[name] not in (None, ""):
            attributes[name] = _number(attributes[name])
        elif name in attributes:
            del attributes[name]
    for name in ("directed", "derived", "inferred", "review_required", "documentary"):
        if name in attributes:
            value = str(attributes[name]).strip().lower()
            if value not in {"true", "false"}:
                raise ValueError(f"Colonne {name} : littéral true ou false attendu.")
            attributes[name] = value == "true"
    if "rotation" in attributes:
        value = attributes["rotation"]
        attributes["rotation"] = _text_rotation(value) if value not in (None, "") else 0
    return attributes


def _document_context(text):
    if _DOCUMENT_FIELD.search(text) or _DOCUMENT_FILE.search(text) or _DOCUMENT_REFERENCE.search(text):
        return True
    # Narrative compliance references are not equipment declarations. Keep short
    # isolated tags and ordinary equipment descriptions, even near a notes area.
    return bool(_REGULATORY_TEXT.search(text) and len(re.findall(r"\b[A-Za-z]{2,}\b", text)) >= 8)


def _drawing_contexts(rows, width, height, *, labels=(), contexts=None):
    """Associate only nearby, explicitly named title-block fields with their value.

    This is not a blanket border exclusion: real equipment can occur near a border.
    OCR provides text centres only; PDF vector fields supply their actual bounds.
    """
    labels = list(labels)
    for text, x, y, _ in rows:
        if _DOCUMENT_FIELD.search(text):
            labels.append((text, x, y, width * .06, height * .025))
    result = []
    for index, (text, x, y, _) in enumerate(rows):
        context = contexts[index] if contexts is not None else text
        for label, field_x, field_y, field_width, field_height in labels:
            if field_x < width * .75 and field_y < height * .75:
                continue
            if (abs(x - field_x) <= min(width * .10, max(24, field_width * 1.2))
                    and 0 <= y - field_y <= min(height * .08, max(16, field_height * 6))):
                context += f" ; champ documentaire : {label}"
                break
        result.append(context)
    return result


def _add_tags(doc, rows, page, provenance, *, contexts=None):
    used = {item.id for item in doc.equipment}
    added = 0
    existing = {(item.source_tag.upper(), item.page, round(item.position.x / 8), round(item.position.y / 8))
                for item in doc.equipment}
    for index, (text, x, y, confidence) in enumerate(rows):
        context = contexts[index] if contexts is not None else text
        for match in _TAG.finditer(text):
            tag = re.sub(r"\s+", "", match[0].upper())
            ambiguous_at = bool(re.fullmatch(r"(?:\d+-)?AT-?\d.*", tag))
            if _document_context(context):
                _warn(doc, "Repères de noms de fichiers, champs de cartouche ou paragraphes réglementaires écartés des équipements ; texte et aperçu conservés pour revue.")
                continue
            # Unhyphenated words such as A4 are usually sheet sizes, not tags.
            if "-" not in tag and _kind(tag) == "unknown" and not ambiguous_at:
                continue
            key = (tag, page, round(x / 8), round(y / 8))
            if key in existing:
                continue
            if len(doc.equipment) >= MAX_ITEMS:
                raise ValueError("Plus de 2 000 équipements/tags ; importer moins de pages.")
            existing.add(key)
            kind = _kind(tag)
            detail = ""
            if ambiguous_at:
                detail = " ; préfixe AT ambigu, légende requise"
                _warn(doc, "Préfixe AT ambigu (transmetteur d'analyse ou cuve selon la légende) : type inconnu conservé pour revue, sans déduction du symbole.")
            doc.equipment.append(PidEquipment(id=_id(tag, used), name=tag, type=kind, source_tag=tag,
                                             position=PidPosition(x=x, y=y), page=page,
                                             confidence=min(0.85, max(0.0, confidence)),
                                             provenance=f"{provenance} ; texte : {_text(context, 600)}{detail}",
                                             review_required=True))
            added += 1
    return added


def _png(image, budget=3_990_000):
    image = image.convert("RGB")
    image.thumbnail((2000, 2000))
    for _ in range(12):
        output = io.BytesIO()
        image.save(output, format="PNG", optimize=True)
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        if len(encoded) + 22 <= budget:
            return "data:image/png;base64," + encoded
        image.thumbnail((int(image.width * .7), int(image.height * .7)))
    raise ValueError("Aperçu trop volumineux.")


def _fit_document(doc):
    """Keep the persisted result within the project API's finite payload budget."""
    illustrated = [page for page in doc.pages if page.image_data_url]
    budget = MAX_PREVIEWS // max(1, len(illustrated))
    for page in illustrated:
        if len(page.image_data_url) <= budget:
            continue
        Image, _ = _pillow()
        with Image.open(io.BytesIO(base64.b64decode(page.image_data_url.split(",", 1)[1]))) as image:
            if image.width * image.height > MAX_PIXELS:
                raise ValueError("Dimensions d'aperçu PNG hors limites.")
            page.image_data_url = _png(image.copy(), budget=budget)
        _warn(doc, "Aperçus réduits pour conserver un document P&ID local de taille bornée.")
    remaining_text = 200000
    for page in doc.pages:
        if len(page.text) > remaining_text:
            page.text = page.text[:remaining_text]
            _warn(doc, "Texte source limité à 200 000 caractères pour l'ensemble des pages ; conserver le fichier original.")
        remaining_text -= len(page.text)
    if len(doc.model_dump_json().encode("utf-8")) > MAX_DOCUMENT:
        raise ValueError("Document P&ID extrait trop volumineux (4 Mio) ; importer moins de pages/objets.")
    return doc


def _pillow():
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise ValueError("Lecture d'image indisponible : installer les dépendances P&ID verrouillées.") from exc
    return Image, ImageDraw


def _draw_preview(width, height, segments, rows, circles=()):
    Image, ImageDraw = _pillow()
    scale = min(1.5, 1800 / max(width, height))
    image = Image.new("RGB", (max(1, math.ceil(width * scale)), max(1, math.ceil(height * scale))), "white")
    draw = ImageDraw.Draw(image)
    for start, end in segments:
        draw.line((start[0] * scale, start[1] * scale, end[0] * scale, end[1] * scale), fill="#243449", width=1)
    for x, y, radius in circles:
        draw.ellipse(((x - radius) * scale, (y - radius) * scale,
                      (x + radius) * scale, (y + radius) * scale), outline="#243449")
    for text, x, y, _ in rows:
        draw.text((x * scale, y * scale), text[:200], fill="#0055DD")
    return _png(image)


def _infer_connections(doc, segments, page, width, height):
    """Walk actual touching stroke endpoints; never connect by tag proximity alone.

    Crossings and symbol internals are ambiguous. Every resulting link is
    undirected and inferred. Mid-stroke crossings do not create a junction.
    """
    if len(segments) > MAX_SEGMENTS:
        raise ValueError("Dessin trop complexe : plus de 20 000 segments droits par page.")
    items = [item for item in doc.equipment if item.page == page]
    if len(items) < 2 or not segments:
        return
    tolerance = max(.5, min(width, height) / 1500)
    points, neighbors, grid = [], defaultdict(set), defaultdict(list)

    def vertex(point):
        cell = (math.floor(point[0] / tolerance), math.floor(point[1] / tolerance))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for index in grid[(cell[0] + dx, cell[1] + dy)]:
                    if math.dist(points[index], point) <= tolerance:
                        return index
        index = len(points)
        points.append(point)
        grid[cell].append(index)
        return index

    for start, end in segments:
        a, b = vertex(start), vertex(end)
        if a != b:
            neighbors[a].add(b)
            neighbors[b].add(a)
    anchors = defaultdict(set)
    snap = max(12, min(60, max(width, height) / 35))
    for item in items:
        if not points:
            break
        location = (item.position.x, item.position.y)
        closest = min(range(len(points)), key=lambda n: math.dist(points[n], location))
        if math.dist(points[closest], location) <= snap:
            anchors[closest].add(item.id)
    pairs = set()
    for origin, origin_items in anchors.items():
        queue, seen = deque([origin]), {origin}
        while queue:
            current = queue.popleft()
            if current != origin and current in anchors:
                for a in origin_items:
                    for b in anchors[current]:
                        if a != b:
                            pairs.add(tuple(sorted((a, b))))
                continue
            for following in neighbors[current]:
                if following not in seen:
                    seen.add(following)
                    queue.append(following)
    for a, b in sorted(pairs):
        if len(doc.connections) >= 5000:
            raise ValueError("Plus de 5 000 liaisons candidates ; importer moins de pages.")
        doc.connections.append(PidConnection(id=f"link_{len(doc.connections) + 1}", source=a, target=b,
                                             label="Tracé candidat à vérifier", directed=False,
                                             inferred=True, confidence=.35))
    if pairs:
        _warn(doc, "Liaisons déduites de tracés droits et de tags voisins : jonctions, symboles et sens doivent être revus.")


def _drawing_warning(doc):
    _warn(doc, "Brouillon documentaire : tags, types et liaisons extraits doivent être revus. Aucun paramètre physique ni mapping PLC n'est déduit.")
    if not doc.equipment:
        _warn(doc, "Aucun tag reconnu ; l'aperçu reste disponible pour la saisie manuelle.")


def _raster(data, doc, pages, ocr):
    Image, _ = _pillow()
    try:
        with Image.open(io.BytesIO(data)) as source:
            chosen = _selection(pages, getattr(source, "n_frames", 1), doc)
            for index in chosen:
                source.seek(index)
                if source.width * source.height > MAX_PIXELS:
                    raise ValueError("Image trop grande : 30 millions de pixels par page au maximum.")
                image = source.convert("RGB")
                image.thumbnail((2400, 2400))
                rows = []
                if ocr:
                    from .pid_ocr import recognize
                    rows = recognize(image)
                else:
                    _warn(doc, "OCR désactivé ; aucun tag n'est extrait des pages raster.")
                _add_tags(doc, rows, index + 1, "OCR local CPU, position en pixels d'aperçu",
                          contexts=_drawing_contexts(rows, image.width, image.height))
                doc.pages.append(PidPage(number=index + 1, width=image.width, height=image.height,
                                          image_data_url=_png(image.copy()), text="\n".join(row[0] for row in rows)[:200000]))
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("Image trop grande pour une lecture locale bornée.") from exc
    except (OSError, EOFError) as exc:
        raise ValueError("Image P&ID illisible ou format non pris en charge.") from exc
    _warn(doc, "Une image fournit des tags OCR et un fond de plan ; aucune topologie de tuyauterie n'est reconnue automatiquement.")
    _drawing_warning(doc)
    return doc


def _png_embedded(data):
    """Read only our bounded native PNG chunk; Pillow limits arbitrary text too."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    offset = 8
    while offset + 12 <= len(data):
        size = int.from_bytes(data[offset:offset + 4], "big")
        kind = data[offset + 4:offset + 8]
        if offset + size + 12 > len(data):
            raise ValueError("PNG tronqué.")
        value = data[offset + 8:offset + 8 + size]
        if kind in {b"tEXt", b"zTXt"} and value.startswith(b"fat-studio-pid\x00"):
            checksum = int.from_bytes(data[offset + 8 + size:offset + 12 + size], "big")
            if zlib.crc32(kind + value) != checksum:
                raise ValueError("Métadonnées PNG corrompues (CRC).")
            payload = value[len(b"fat-studio-pid\x00"):]
            if kind == b"zTXt":
                if not payload or payload[0] != 0:
                    raise ValueError("Compression de métadonnées PNG non prise en charge.")
                decoder = zlib.decompressobj()
                try:
                    payload = decoder.decompress(payload[1:], MAX_DOCUMENT + 1)
                except zlib.error as exc:
                    raise ValueError("Métadonnées PNG illisibles.") from exc
                if decoder.unconsumed_tail or not decoder.eof:
                    raise ValueError("Métadonnées PNG trop volumineuses ou incomplètes.")
            if len(payload) > MAX_DOCUMENT:
                raise ValueError("Métadonnées PNG trop volumineuses (4 Mio).")
            return _native(_json(payload))
        offset += size + 12
    return None


def _pdf_line_context(text_page, char_index, length):
    """Retain the matching line using native character indices, not string offsets."""
    start = max(0, char_index - 240)
    before = text_page.get_text_range(start, char_index - start) if char_index > start else ""
    after = text_page.get_text_range(char_index, min(length + 240, text_page.count_chars() - char_index))
    return before.rsplit("\n", 1)[-1] + after.split("\n", 1)[0]


def _pdf_document_labels(page, text_page, width, height):
    labels = []
    for label in ("FILENAME", "FILE NAME", "DRAWING NUMBER", "DRAWING NO", "DWG NO", "DWG NUMBER", "SHEET NUMBER", "SHEET NO", "PROJECT NUMBER"):
        with closing(text_page.search(label, match_case=False)) as search:
            while (found := search.get_next()) is not None:
                index, count = found
                boxes = [text_page.get_charbox(i) for i in range(index, index + count)]
                left, bottom = min(b[0] for b in boxes), min(b[1] for b in boxes)
                right, top = max(b[2] for b in boxes), max(b[3] for b in boxes)
                x1, y1 = _pdf_point(page, width, height, left, bottom)
                x2, y2 = _pdf_point(page, width, height, right, top)
                labels.append((label, (x1 + x2) / 2, (y1 + y2) / 2, abs(x2 - x1), abs(y2 - y1)))
                if len(labels) >= 200:
                    return labels
    return labels


def _pdf_segments(page, width, height, raw, doc, page_number):
    segments = []
    try:
        for count, obj in enumerate(page.get_objects(max_depth=4)):
            if count >= MAX_SEGMENTS:
                raise _PdfGeometryLimit
            if obj.type != raw.FPDF_PAGEOBJ_PATH:
                continue
            if obj.level:
                _warn(doc, "Tracés imbriqués dans des formulaires PDF non utilisés pour déduire la topologie.")
                continue
            matrix = obj.get_matrix()
            previous = first = None
            count_segments = raw.FPDFPath_CountSegments(obj.raw)
            if count_segments > MAX_SEGMENTS:
                raise _PdfGeometryLimit
            for segment_index in range(count_segments):
                segment = raw.FPDFPath_GetPathSegment(obj.raw, segment_index)
                x, y = ctypes.c_float(), ctypes.c_float()
                if not raw.FPDFPathSegment_GetPoint(segment, x, y):
                    continue
                point = _pdf_point(page, width, height,
                                   matrix.a * x.value + matrix.c * y.value + matrix.e,
                                   matrix.b * x.value + matrix.d * y.value + matrix.f)
                kind = raw.FPDFPathSegment_GetType(segment)
                if kind == raw.FPDF_SEGMENT_MOVETO:
                    previous = first = point
                elif kind == raw.FPDF_SEGMENT_LINETO and previous:
                    segments.append((previous, point))
                    previous = point
                else:
                    previous = None
                if raw.FPDFPathSegment_GetClose(segment) and previous and first:
                    segments.append((previous, first))
                    previous = first
                if len(segments) > MAX_SEGMENTS:
                    raise _PdfGeometryLimit
    except _PdfGeometryLimit:
        _warn(doc, f"Page {page_number} : limite de géométrie PDF atteinte ({MAX_SEGMENTS:,} objets/segments au maximum) ; analyse des tracés incomplète, toutes les liaisons de cette page sont ignorées. Aperçu, texte et tags restent disponibles pour revue.")
        return []
    return segments


def _pdf(data, doc, pages, ocr):
    try:
        import pypdfium2 as pdfium
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("Lecture PDF indisponible : installer les dépendances P&ID verrouillées.") from exc
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ValueError("PDF chiffré : fournir une copie non chiffrée.")
        # Native exports carry the exact interchange beside their visual pages.
        if "fat-studio-pid.json" in reader.attachments:
            attachments = reader.attachments["fat-studio-pid.json"]
            if len(attachments) != 1 or len(attachments[0]) > MAX_UPLOAD:
                raise ValueError("Pièce jointe P&ID native invalide ou trop grande.")
            embedded = _native(_json(attachments[0]))
            _warn(embedded, "Données P&ID natives incorporées dans le PDF relues ; le dessin externe peut différer de ces données.")
            return embedded
        with _PDF_LOCK, pdfium.PdfDocument(data) as pdf:
            chosen = _selection(pages, len(pdf), doc)
            for index in chosen:
                with closing(pdf[index]) as page:
                    width, height = page.get_size()
                    if not (0 < width <= 100000 and 0 < height <= 100000):
                        raise ValueError("Dimensions PDF hors limites.")
                    rows, contexts = [], []
                    with closing(page.get_textpage()) as text_page:
                        if text_page.count_chars() > 200000:
                            raise ValueError("Page PDF trop complexe : plus de 200 000 caractères.")
                        text = text_page.get_text_bounded()
                        # Locate each tag with PDFium's character index, not Python string offsets.
                        for tag in dict.fromkeys(match[0] for match in _TAG.finditer(text)):
                            with closing(text_page.search(tag, match_case=False)) as search:
                                while (found := search.get_next()) is not None:
                                    char_index, length = found
                                    left, bottom, right, top = text_page.get_charbox(char_index)
                                    x, y = _pdf_point(page, width, height, (left + right) / 2, (bottom + top) / 2)
                                    rows.append((tag, x, y, .85))
                                    contexts.append(_pdf_line_context(text_page, char_index, length))
                                    if len(rows) > 10000:
                                        raise ValueError("Page PDF trop complexe : trop de tags candidats.")
                        labels = _pdf_document_labels(page, text_page, width, height)
                        contexts = _drawing_contexts(rows, width, height, labels=labels, contexts=contexts)
                    segments = _pdf_segments(page, width, height, pdfium.raw, doc, index + 1)
                    bitmap = page.render(scale=min(2.5, 2400 / max(width, height)))
                    try:
                        image = bitmap.to_pil().copy()
                    finally:
                        bitmap.close()
                    added = _add_tags(doc, rows, index + 1, "PDF : texte vectoriel positionné, coordonnées de page", contexts=contexts)
                    if not added and ocr:
                        from .pid_ocr import recognize
                        rows = [(text, x * width / image.width, y * height / image.height, confidence)
                                for text, x, y, confidence in recognize(image)]
                        ocr_text = "\n".join(row[0] for row in rows)
                        text = (text + "\n[OCR local]\n" if text.strip() else "") + ocr_text
                        _warn(doc, "Page sans tags vectoriels exploitables : OCR local CPU utilisé. La géométrie raster ne prouve pas les liaisons.")
                        _add_tags(doc, rows, index + 1, "PDF : OCR local CPU, coordonnées de page",
                                  contexts=_drawing_contexts(rows, width, height))
                    elif not added:
                        _warn(doc, "Page sans tags vectoriels exploitables et OCR désactivé ; aperçu et texte conservés pour revue manuelle.")
                    _infer_connections(doc, segments, index + 1, width, height)
                    doc.pages.append(PidPage(number=index + 1, width=width, height=height,
                                              image_data_url=_png(image), text=text[:200000]))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"PDF P&ID illisible : {type(exc).__name__}.") from exc
    _drawing_warning(doc)
    return doc


def _pdf_point(page, width, height, x, y):
    """PDFium accounts for the page crop and intrinsic rotation in this mapping."""
    import pypdfium2
    target_x, target_y = ctypes.c_long(), ctypes.c_long()
    if not pypdfium2.raw.FPDF_PageToDevice(page.raw, 0, 0, round(width * 4), round(height * 4), 0,
                                         x, y, target_x, target_y):
        raise ValueError("Coordonnées PDF impossibles à projeter sur la page.")
    return (target_x.value / 4, target_y.value / 4)


def _xml(data):
    try:
        from defusedxml.ElementTree import fromstring
        root = fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except ImportError as exc:
        raise ValueError("Lecture XML indisponible : installer les dépendances P&ID verrouillées.") from exc
    except Exception as exc:
        raise ValueError("XML P&ID illisible ou DTD/entités externes interdites.") from exc
    stack, count = [(root, 0)], 0
    while stack:
        element, depth = stack.pop()
        count += 1
        if depth > 40 or count > MAX_XML_ELEMENTS:
            raise ValueError("XML P&ID trop complexe.")
        stack.extend((child, depth + 1) for child in element)
    return root


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _matrix(transform):
    result = (1., 0., 0., 1., 0., 0.)
    if re.sub(r"[A-Za-z]+\s*\([^)]*\)", "", transform).strip(" ,\t\r\n"):
        raise ValueError("Transformation SVG invalide.")
    for name, args in re.findall(r"([A-Za-z]+)\s*\(([^)]*)\)", transform):
        if re.sub(_NUMBER, "", args).strip(" ,\t\r\n"):
            raise ValueError("Arguments de transformation SVG invalides.")
        values = [_number(value) for value in re.findall(_NUMBER, args)]
        if name == "matrix" and len(values) == 6:
            addition = tuple(values)
        elif name == "translate" and 1 <= len(values) <= 2:
            addition = (1, 0, 0, 1, values[0], values[1] if len(values) > 1 else 0)
        elif name == "scale" and 1 <= len(values) <= 2:
            addition = (values[0], 0, 0, values[-1], 0, 0)
        elif name == "rotate" and len(values) in (1, 3):
            angle = math.radians(values[0])
            c, s = math.cos(angle), math.sin(angle)
            cx, cy = values[1:] if len(values) == 3 else (0, 0)
            addition = (c, s, -s, c, cx - c * cx + s * cy, cy - s * cx - c * cy)
        else:
            raise ValueError(f"Transformation SVG non prise en charge : {name}.")
        result = _multiply(result, addition)
    return result


def _multiply(a, b):
    return (a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1],
            a[0] * b[2] + a[2] * b[3], a[1] * b[2] + a[3] * b[3],
            a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5])


def _point(matrix, x, y):
    x, y = _number(x), _number(y)
    return (_number(matrix[0] * x + matrix[2] * y + matrix[4]),
            _number(matrix[1] * x + matrix[3] * y + matrix[5]))


def _svg(data, doc):
    root = _xml(data)
    if _local(root.tag) != "svg":
        raise ValueError("Le fichier n'est pas un SVG.")
    for element in root.iter():
        if _local(element.tag) == "metadata" and element.get("id") == "fat-studio-pid":
            embedded = _native(_json(element.text or ""))
            _warn(embedded, "Données P&ID natives incorporées dans le SVG relues ; le dessin externe peut différer de ces données.")
            return embedded
    viewbox = [_number(value) for value in re.findall(_NUMBER, root.get("viewBox", ""))]
    if root.get("viewBox") is not None and len(viewbox) != 4:
        raise ValueError("viewBox SVG invalide : quatre nombres attendus.")
    if len(viewbox) == 4:
        minx, miny, width, height = viewbox
    else:
        minx = miny = 0
        width = _svg_coordinate(root.get("width", "1000"))
        height = _svg_coordinate(root.get("height", "700"))
    if width <= 0 or height <= 0:
        raise ValueError("Dimensions SVG invalides.")
    rows, segments, circles = [], [], []
    stack = [(root, (1, 0, 0, 1, -minx, -miny))]
    while stack:
        element, parent_matrix = stack.pop()
        kind = _local(element.tag)
        if kind in {"defs", "metadata", "script", "style", "foreignObject"}:
            continue
        matrix = _multiply(parent_matrix, _matrix(element.get("transform", "")))
        stack.extend((child, matrix) for child in reversed(element))
        get = element.get
        if kind == "text":
            x = _svg_coordinate(get("x", "0"))
            y = _svg_coordinate(get("y", "0"))
            px, py = _point(matrix, x, y)
            rows.append(("".join(element.itertext()), px, py, .8))
        elif kind == "line":
            segments.append((_point(matrix, get("x1", 0), get("y1", 0)),
                             _point(matrix, get("x2", 0), get("y2", 0))))
        elif kind in {"polyline", "polygon"}:
            values = re.findall(_NUMBER, get("points", ""))
            if len(values) % 2:
                raise ValueError("Points SVG invalides.")
            points = [_point(matrix, values[i], values[i + 1]) for i in range(0, len(values), 2)]
            segments.extend(zip(points, points[1:]))
            if kind == "polygon" and points:
                segments.append((points[-1], points[0]))
        elif kind == "rect":
            x, y, w, h = (_number(get(key, 0)) for key in ("x", "y", "width", "height"))
            points = [_point(matrix, px, py) for px, py in ((x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y))]
            segments.extend(zip(points, points[1:]))
        elif kind in {"circle", "ellipse"}:
            x, y = _point(matrix, get("cx", 0), get("cy", 0))
            radius = abs(_number(get("r", get("rx", 0))) * matrix[0])
            circles.append((x, y, radius))
        elif kind == "path":
            segments.extend(_svg_path(get("d", ""), matrix, doc))
        elif kind in {"image", "use"}:
            _warn(doc, "SVG : images et symboles référencés non exécutés ; leur géométrie n'est pas extraite.")
        if len(segments) > MAX_SEGMENTS or len(rows) > 10000:
            raise ValueError("SVG trop complexe pour l'import local.")
    _add_tags(doc, rows, 1, "SVG : texte et transformation explicites")
    _infer_connections(doc, segments, 1, width, height)
    doc.pages.append(PidPage(number=1, width=width, height=height,
                              image_data_url=_draw_preview(width, height, segments, rows, circles),
                              text="\n".join(row[0] for row in rows)[:200000]))
    _warn(doc, "Aperçu SVG simplifié en PNG : styles, courbes et ressources externes ne sont pas rendus.")
    _drawing_warning(doc)
    return doc


def _svg_coordinate(value):
    match = re.match(_NUMBER, value.strip())
    if match is None:
        raise ValueError("Coordonnée ou dimension SVG invalide.")
    return _number(match[0])


def _svg_path(value, matrix, doc):
    tokens = re.findall(r"[A-Za-z]|" + _NUMBER, value)
    segments, index, command = [], 0, ""
    current = first = (0., 0.)
    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index]
            index += 1
        if command.upper() == "Z":
            segments.append((_point(matrix, *current), _point(matrix, *first)))
            current, command = first, ""
            continue
        count = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}.get(command.upper())
        if not count or index + count > len(tokens) or any(token.isalpha() for token in tokens[index:index + count]):
            raise ValueError("Tracé SVG invalide.")
        values = [_number(token) for token in tokens[index:index + count]]
        index += count
        relative = command.islower()
        upper = command.upper()
        if upper == "H":
            following = (values[0] + (current[0] if relative else 0), current[1])
        elif upper == "V":
            following = (current[0], values[0] + (current[1] if relative else 0))
        else:
            following = (values[-2] + (current[0] if relative else 0), values[-1] + (current[1] if relative else 0))
        if upper in {"L", "H", "V"}:
            segments.append((_point(matrix, *current), _point(matrix, *following)))
        elif upper == "M":
            first = following
            command = "l" if relative else "L"
        else:
            _warn(doc, "Courbes SVG non utilisées pour déduire des liaisons.")
        current = following
        if len(segments) > MAX_SEGMENTS:
            raise ValueError("Tracé SVG trop complexe.")
    return segments


def _graph(value, doc):
    if not isinstance(value, dict):
        raise ValueError("Le graphe P&ID JSON doit être un objet.")
    if "fat_studio_drawing" in value:
        from .pid_titleblock import PidDrawingSettings
        doc.drawing = PidDrawingSettings.model_validate(value["fat_studio_drawing"])
    nodes, edges = value.get("nodes"), value.get("edges", value.get("links", []))
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("Graphe JSON attendu : listes nodes et edges (ou links).")
    if len(nodes) > MAX_ITEMS or len(edges) > 5000:
        raise ValueError("Graphe limité à 2 000 objets et 5 000 liaisons.")
    used, references, node_types = set(), {}, {}
    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or "id" not in node:
            raise ValueError("Chaque nœud doit fournir un identifiant.")
        source_id = _reference(node["id"])
        if source_id in references:
            raise ValueError("Identifiant de nœud dupliqué dans le graphe.")
        identifier = _id(source_id, used)
        references[source_id] = identifier
        attributes = node.get("attrs", node.get("attributes", node.get("properties", {})))
        attributes = attributes if isinstance(attributes, dict) else {}
        merged = {**attributes, **node}
        position = merged.get("position", merged.get("pos", {}))
        if isinstance(position, list) and len(position) >= 2:
            position = {"x": position[0], "y": position[1]}
        if not isinstance(position, dict):
            position = {}
        x, y = position.get("x", merged.get("x")), position.get("y", merged.get("y"))
        generated = x is None or y is None
        x = index % 8 * 180 + 80 if x is None else _graph_number(x)
        y = index // 8 * 120 + 70 if y is None else _graph_number(y)
        label = _text(merged.get("label") or merged.get("tag") or merged.get("name") or source_id)
        source_kind = merged.get("fat_studio_type") or merged.get("kind") or merged.get("type") or "unknown"
        kind = _explicit_kind(source_kind)
        if str(merged.get("type", "")).lower() == "instrument" and merged.get("role") in {"transmitter", "switch"}:
            kind = "digital_sensor" if merged["role"] == "switch" else "analog_sensor"
        node_types[identifier] = (str(merged.get("type", source_kind)).lower().replace("_", ""), kind)
        confidence = _confidence(merged.get("confidence", .5))
        provenance = _text(merged.get("source_provenance"), 1000) if "source_provenance" in merged else json.dumps({"source_id": source_id, "source_type": merged.get("type"), "source_kind": source_kind,
                                 "provenance": merged.get("provenance", "JSON explicite"),
                                 "layout_generated": generated}, ensure_ascii=False, default=str)[:1000]
        page = merged.get("page", 1)
        if isinstance(merged.get("provenance"), dict):
            page = merged["provenance"].get("page", page)
        elif isinstance(merged.get("provenance"), list):
            page = next((source["page"] for source in merged["provenance"]
                         if isinstance(source, dict) and "page" in source), page)
        page_number = _graph_number(page)
        if not page_number.is_integer():
            raise ValueError("Numéro de page JSON entier attendu.")
        source_tag = merged.get("tag") if "tag" in merged else merged.get("source_tag", source_id)
        doc.equipment.append(PidEquipment(id=identifier, name=label or source_id[:200], type=kind,
                                         source_tag=_text(source_tag),
                                         source_kind=_document_string(merged.get("source_kind", _text(source_kind, 80)), "source_kind"),
                                         rotation=_rotation(merged.get("rotation", 0)),
                                         documentary=_boolean(merged.get("documentary", False)),
                                         position=PidPosition(x=x, y=y), page=int(page_number),
                                         confidence=confidence, provenance=provenance,
                                         review_required=_boolean(merged.get("review_required", True))))
        if generated:
            _warn(doc, "Certains objets n'ont pas de coordonnées : leur disposition est générée pour la revue.")
    flow, used_edges, raw_edges = defaultdict(list), set(), set()
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise ValueError("Chaque liaison du graphe doit être un objet.")
        source, target = _reference(edge.get("source")), _reference(edge.get("target"))
        if source not in references or target not in references:
            raise ValueError("Liaison du graphe vers un nœud absent.")
        attributes = edge.get("attrs", edge.get("attributes", edge.get("properties", {})))
        edge = {**(attributes if isinstance(attributes, dict) else {}), **edge}
        direction = edge.get("directed", value.get("directed", True))
        raw_id = _reference(edge.get("id", f"link_{index + 1}"))
        if str(raw_id) in raw_edges:
            raise ValueError("Identifiant de liaison dupliqué dans le graphe.")
        raw_edges.add(str(raw_id))
        connection = PidConnection(id=_id(raw_id, used_edges), source=references[source], target=references[target],
                                              service=_document_string(edge.get("service", "unspecified"), "service"),
                                              source_port=_document_string(edge.get("source_port", ""), "source_port"),
                                             target_port=_document_string(edge.get("target_port", ""), "target_port"),
                                             label=_text(edge.get("label") if "label" in edge else edge.get("type")),
                                             directed=_boolean(direction), inferred=_boolean(edge.get("derived", edge.get("inferred", False))),
                                             confidence=_confidence(edge.get("confidence", .8)))
        doc.connections.append(connection)
        if str(edge.get("type", "")).upper() == "FLOWS_TO" and connection.directed:
            flow[connection.source].append((connection.target, connection.confidence))
    _contract_flows(doc, node_types, flow)
    plant_name = value.get("plant", {}).get("name") if isinstance(value.get("plant"), dict) else None
    doc.title = _text(value.get("title") or plant_name) or doc.title
    doc.metadata["graph_adapter"] = "ScottDuncanAI / node-link JSON ; types et relations conservés comme données documentaires"
    for issue in value.get("issues", []) if isinstance(value.get("issues"), list) else []:
        if isinstance(issue, dict) and issue.get("message"):
            _warn(doc, _text(issue["message"], 2000))
    _warn(doc, "Graphe documentaire importé : types et relations explicites conservés, sans traduction des boucles en logique PLC.")
    return doc


def _contract_flows(doc, node_types, flow):
    passthrough = {identifier for identifier, (source_type, kind) in node_types.items()
                   if source_type in {"pipesegment", "offpageconnector"} or kind.lower().replace("_", "") in {"pipesegment", "offpageconnector"}}
    excluded = {identifier for identifier, (source_type, _) in node_types.items()
                if source_type in {"plant", "sheet", "controlloop"}}
    existing = {(origin, target) for origin, targets in flow.items() for target, _ in targets}
    existing.update((edge.source, edge.target) for edge in doc.connections if edge.label.upper() == "FEEDS")
    confidence_by_id = {item.id: item.confidence for item in doc.equipment}
    derived = 0
    for origin in flow:
        if origin in passthrough or origin in excluded:
            continue
        queue = deque((target, confidence, [target]) for target, confidence in flow[origin] if target in passthrough)
        seen = set()
        while queue:
            current, confidence, path = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            confidence = min(confidence, confidence_by_id[current])
            for target, edge_confidence in flow.get(current, []):
                combined = min(confidence, edge_confidence)
                if target in passthrough:
                    if target not in seen:
                        queue.append((target, combined, path + [target]))
                elif target != origin and target not in excluded and (origin, target) not in existing:
                    if len(doc.connections) >= 5000:
                        _warn(doc, "Limite de 5 000 liaisons atteinte : certaines propositions via tuyauterie ne sont pas ajoutées.")
                        return
                    existing.add((origin, target))
                    edge_id = _id(f"flow_{len(doc.connections) + 1}", {edge.id for edge in doc.connections})
                    doc.connections.append(PidConnection(id=edge_id, source=origin, target=target,
                                                         label=_text("FLOWS_TO via " + ", ".join(path)),
                                                         directed=True, inferred=True,
                                                         confidence=min(combined, confidence_by_id[origin], confidence_by_id[target])))
                    derived += 1
    if derived:
        _warn(doc, f"{derived} liaison(s) FLOWS_TO proposée(s) en traversant uniquement PipeSegment/OffPageConnector ; nœuds et relations d'origine conservés, revue nécessaire.")


def _graphml(root, doc):
    for element in root.iter():
        if _local(element.tag) == "data" and element.get("key") == "pid_document" and element.text:
            return _native(_json(element.text))
    keys = {element.get("id"): element.get("attr.name", element.get("id")) for element in root
            if _local(element.tag) == "key"}
    nodes, edges = [], []
    directed = True
    for element in root.iter():
        kind = _local(element.tag)
        if kind == "graph":
            if element.get("edgedefault", "directed") not in {"directed", "undirected"}:
                raise ValueError("GraphML : edgedefault doit être directed ou undirected.")
            directed = element.get("edgedefault", "directed") == "directed"
        if kind not in {"node", "edge"}:
            continue
        attributes = {keys.get(child.get("key"), child.get("key")): child.text
                      for child in element if _local(child.tag) == "data" and child.text}
        attributes = _text_attributes(attributes)
        if kind == "node":
            nodes.append({**attributes, "id": element.get("id", "")})
        else:
            direction = _text_attributes({"directed": element.get("directed", str(directed))})["directed"]
            edges.append({**attributes, "source": element.get("source"), "target": element.get("target"),
                          "directed": direction})
    return _graph({"nodes": nodes, "edges": edges, "directed": directed}, doc)


def _dexpi(root, doc):
    used, references, nodes = set(), {}, []
    kinds = {"Equipment", "Nozzle", "PipingComponent", "Component", "PipingNetworkSegment",
             "ProcessInstrument", "ProcessInstrumentationFunction", "InstrumentationLoopFunction",
             "PipeConnectorSymbol", "ActuatingFunction", "InformationFlow", "PropertyBreak"}
    parents = {child: parent for parent in root.iter() for child in parent}
    for element in root.iter():
        kind = _local(element.tag)
        if not element.get("ID") or (kind not in kinds and not element.get("ComponentClass")):
            continue
        ancestor = parents.get(element)
        catalogue = False
        while ancestor is not None:
            if _local(ancestor.tag) == "ShapeCatalogue":
                catalogue = True
                break
            ancestor = parents.get(ancestor)
        if catalogue:
            continue
        raw = element.get("ID")
        if raw in references:
            raise ValueError("Identifiant DEXPI dupliqué.")
        if len(nodes) >= MAX_ITEMS:
            raise ValueError("DEXPI limité à 2 000 objets.")
        references[raw] = _id(raw, used)
        nodes.append(element)
    for index, element in enumerate(nodes):
        raw, kind = element.get("ID"), _local(element.tag)
        tag = element.get("TagName") or element.get("ComponentName") or raw
        location = next((child for position in element if _local(position.tag) == "Position"
                         for child in position if _local(child.tag) == "Location"), None)
        x, y = (index % 8 * 180 + 80, index // 8 * 120 + 70) if location is None else (
            _number(location.get("X", 0)), -_number(location.get("Y", 0)))
        source_type = element.get("ComponentClass") or kind
        doc.equipment.append(PidEquipment(id=references[raw], name=_text(tag), source_tag=_text(tag),
                                         source_kind=_text(element.get("source_kind") or source_type, 80),
                                         rotation=_text_rotation(element.get("rotation", 0)),
                                         type=_explicit_kind(source_type), position=PidPosition(x=x, y=y),
                                         confidence=1, provenance=f"DEXPI/Proteus XML ; ID={raw} ; classe={source_type}"[:1000]))
        if location is None:
            _warn(doc, "DEXPI : positions absentes disposées automatiquement pour la revue.")
    for element in root.iter():
        if _local(element.tag) != "Connection":
            continue
        source, target = element.get("FromID"), element.get("ToID")
        owner = parents.get(element)
        owner_id = owner.get("ID") if owner is not None else None
        if not source and owner_id in references:
            source = owner_id
        if not target and owner_id in references:
            target = owner_id
        if not source or not target:
            _warn(doc, "DEXPI : référence de connexion incomplète non convertie.")
            continue
        if source not in references or target not in references:
            _warn(doc, "DEXPI : connexion vers un objet non pris en charge ou absent, non convertie.")
            continue
        if len(doc.connections) >= 5000:
            raise ValueError("DEXPI limité à 5 000 liaisons.")
        doc.connections.append(PidConnection(id=f"link_{len(doc.connections) + 1}", source=references[source],
                                             target=references[target], label="Référence XML explicite",
                                             source_port=_text(element.get("source_port"), 80),
                                             target_port=_text(element.get("target_port"), 80),
                                             directed=False, inferred=False, confidence=1))
    if not nodes:
        raise ValueError("XML non reconnu : objets DEXPI/Proteus avec ID attendus.")
    _warn(doc, "DEXPI/Proteus partiel : objets identifiés, positions et références FromID/ToID uniquement ; attributs métier et symboles non interprétés.")
    doc.metadata["dexpi_subset"] = "Plant items ID/TagName/ComponentClass, Position/Location, Connection FromID/ToID ; no schema conformance claimed"
    return doc


def _csv(data, doc):
    try:
        text = data.decode("utf-8-sig")
        try:
            dialect = csv.Sniffer().sniff(text[:8000], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        rows = []
        for index, row in enumerate(reader):
            if index >= MAX_ITEMS:
                raise ValueError("CSV limité à 2 000 équipements.")
            row = {str(key).strip().lower(): value for key, value in row.items() if key is not None}
            tag = row.get("tag") or row.get("source_tag") or row.get("id") or row.get("name")
            if not tag:
                raise ValueError("CSV : colonne tag, id ou name requise pour chaque équipement.")
            row = _text_attributes(row)
            rows.append({**row, "id": row.get("id") or tag, "tag": tag,
                         "label": row.get("name") or tag, "kind": row.get("type") or "unknown"})
        if not rows:
            raise ValueError("CSV sans équipement.")
        return _graph({"nodes": rows, "edges": []}, doc)
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("CSV illisible ; UTF-8 et séparateur virgule, point-virgule ou tabulation attendus.") from exc


def _archive(data):
    """Only the named native document is read; no path is ever extracted."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > 100 or sum(info.file_size for info in infos) > MAX_UPLOAD:
                raise ValueError("Archive P&ID trop volumineuse ou trop complexe.")
            native = [info for info in infos if info.filename == "fat-studio-pid.json"]
            if len(native) != 1 or native[0].file_size > MAX_DOCUMENT:
                raise ValueError("Archive attendue : une entrée fat-studio-pid.json, 4 Mio au maximum.")
            with archive.open(native[0]) as stream:
                payload = stream.read(MAX_DOCUMENT + 1)
            if len(payload) > MAX_DOCUMENT:
                raise ValueError("Archive P&ID décompressée trop volumineuse.")
            return _native(_json(payload))
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise ValueError("Archive P&ID ZIP illisible ou chiffrée.") from exc


def _dxf(data, doc):
    try:
        import ezdxf
    except ImportError as exc:
        raise ValueError("Lecture DXF indisponible : installer les dépendances P&ID verrouillées.") from exc
    try:
        if data.startswith(b"AutoCAD Binary DXF"):
            from ezdxf.lldxf.tagger import binary_tags_loader
            drawing = ezdxf.document.Drawing.load(binary_tags_loader(data))
        else:
            # Pre-2007 DXF is commonly ANSI_1252; native JSON chunks are ASCII.
            from ezdxf.tools.codepage import toencoding
            header = data[:100000].decode("ascii", errors="ignore")
            codepage = re.search(r"\$DWGCODEPAGE\s+\d+\s+([^\s]+)", header)
            version = re.search(r"\$ACADVER\s+\d+\s+(AC\d+)", header)
            encoding = "utf-8-sig"
            if version and version[1] < "AC1021":
                encoding = toencoding(codepage[1]) if codepage else "cp1252"
            try:
                text = data.decode(encoding)
            except (UnicodeError, LookupError) as exc:
                raise ValueError("Encodage DXF invalide ; fournir un export DXF UTF-8 ou une page ANSI déclarée.") from exc
            drawing = ezdxf.read(io.StringIO(text.replace("\r\n", "\n").replace("\r", "\n")))
        if "FAT_STUDIO_PID" in drawing.rootdict:
            record = drawing.rootdict["FAT_STUDIO_PID"]
            embedded = "".join(str(tag.value) for tag in record.tags if tag.code == 1)
            if len(embedded.encode("utf-8")) > MAX_UPLOAD:
                raise ValueError("P&ID natif DXF trop volumineux.")
            result = _native(_json(embedded))
            _warn(result, "Données P&ID natives incorporées dans le DXF relues ; le dessin externe peut différer de ces données.")
            return result
        rows, segments, circles, blocks = [], [], [], []
        entities = list(drawing.modelspace())
        if len(entities) > MAX_SEGMENTS:
            raise ValueError("DXF trop complexe : 20 000 entités au maximum.")
        for entity in entities:
            kind = entity.dxftype()
            if kind in {"TEXT", "MTEXT", "ATTRIB"}:
                text = entity.plain_text() if kind == "MTEXT" else entity.dxf.text
                point = entity.dxf.insert
                rows.append((text, _number(point.x), -_number(point.y), .8))
            elif kind == "LINE":
                start, end = entity.dxf.start, entity.dxf.end
                segments.append(((_number(start.x), -_number(start.y)), (_number(end.x), -_number(end.y))))
            elif kind in {"LWPOLYLINE", "POLYLINE"}:
                if kind == "LWPOLYLINE":
                    points = list(entity.get_points("xyb"))
                else:
                    points = [(vertex.dxf.location.x, vertex.dxf.location.y, vertex.dxf.get("bulge", 0))
                              for vertex in entity.vertices]
                if len(points) > MAX_SEGMENTS:
                    raise ValueError("Polyligne DXF trop complexe.")
                converted = [(_number(point[0]), -_number(point[1])) for point in points]
                for index in range(len(converted) - 1):
                    if not points[index][2]:
                        segments.append((converted[index], converted[index + 1]))
                if entity.is_closed and converted and not points[-1][2]:
                    segments.append((converted[-1], converted[0]))
            elif kind == "CIRCLE":
                point = entity.dxf.center
                circles.append((_number(point.x), -_number(point.y), abs(_number(entity.dxf.radius))))
            elif kind == "INSERT":
                point = entity.dxf.insert
                label = " ".join(attribute.dxf.text for attribute in entity.attribs) or entity.dxf.name
                blocks.append((label, _number(point.x), -_number(point.y), entity.dxf.name))
                rows.append((label, _number(point.x), -_number(point.y), .8))
            else:
                _warn(doc, f"DXF : entité {kind} conservée dans la source, sans géométrie interprétée.")
            if len(segments) > MAX_SEGMENTS:
                raise ValueError("DXF trop complexe : plus de 20 000 segments droits.")
        all_points = [point for segment in segments for point in segment]
        all_points += [(row[1], row[2]) for row in rows]
        all_points += [(x - r, y - r) for x, y, r in circles] + [(x + r, y + r) for x, y, r in circles]
        minx = min((point[0] for point in all_points), default=0) - 30
        miny = min((point[1] for point in all_points), default=0) - 30
        width = max(100, max((point[0] for point in all_points), default=1000) - minx + 30)
        height = max(100, max((point[1] for point in all_points), default=700) - miny + 30)
        if max(width, height) > 100000:
            raise ValueError("Étendue DXF supérieure à 100 000 unités ; normaliser le dessin.")
        rows = [(text, x - minx, y - miny, confidence) for text, x, y, confidence in rows]
        segments = [((a[0] - minx, a[1] - miny), (b[0] - minx, b[1] - miny)) for a, b in segments]
        circles = [(x - minx, y - miny, radius) for x, y, radius in circles]
        _add_tags(doc, rows, 1, "DXF : texte/attributs, coordonnées du dessin normalisées")
        used = {item.id for item in doc.equipment}
        for label, x, y, block_name in blocks:
            if any(math.dist((item.position.x, item.position.y), (x - minx, y - miny)) < 2 for item in doc.equipment):
                continue
            if len(doc.equipment) >= MAX_ITEMS:
                raise ValueError("DXF limité à 2 000 équipements/blocs.")
            doc.equipment.append(PidEquipment(id=_id(block_name, used), name=_text(label) or block_name,
                                             type="unknown", position=PidPosition(x=x - minx, y=y - miny),
                                             confidence=.4, provenance=f"DXF INSERT ; bloc={block_name}"[:1000]))
        _infer_connections(doc, segments, 1, width, height)
        doc.pages.append(PidPage(number=1, width=width, height=height,
                                  image_data_url=_draw_preview(width, height, segments, rows, circles),
                                  text="\n".join(row[0] for row in rows)[:200000]))
        _warn(doc, "Aperçu DXF simplifié : espace objet, textes, lignes, polylignes droites et cercles. Blocs inconnus conservés à revoir ; courbes et présentations non interprétées.")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"DXF illisible ou non pris en charge : {type(exc).__name__}.") from exc
    _drawing_warning(doc)
    return doc


def inspect_pid(data: bytes, filename: str, *, pages: str = "", ocr: bool = True) -> PidDocument:
    """Inspect a local upload without creating/mutating a FAT project."""
    if not isinstance(data, bytes) or not data:
        raise ValueError("Fichier P&ID vide.")
    if len(data) > MAX_UPLOAD:
        raise ValueError("Fichier P&ID limité à 20 Mio.")
    name = PurePosixPath(filename.replace("\\", "/")).name[:240]
    extension = PurePosixPath(name).suffix.lower().lstrip(".")
    doc = PidDocument(source_name=name, title=PurePosixPath(name).stem[:200] or "P&ID importé",
                      source_format=extension or "unknown", source_sha256=hashlib.sha256(data).hexdigest())
    try:
        if extension == "pdf" or data.startswith(b"%PDF-"):
            result = _pdf(data, doc, pages, ocr)
            extension = "pdf"
        elif extension in {"png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp"}:
            result = _png_embedded(data) if extension == "png" else None
            if result is not None:
                _warn(result, "Données P&ID natives incorporées dans le PNG relues ; l'image externe peut différer de ces données.")
            else:
                result = _raster(data, doc, pages, ocr)
        elif extension in {"json", "pid"}:
            value = _json(data)
            result = _native(value) if isinstance(value, dict) and value.get("format") == "fat-studio/pid" else _graph(value, doc)
        elif extension == "svg":
            _selection(pages, 1, doc)
            result = _svg(data, doc)
        elif extension == "dxf":
            _selection(pages, 1, doc)
            result = _dxf(data, doc)
        elif extension == "dwg":
            _selection(pages, 1, doc)
            from .pid_cad import dwg_to_dxf
            converted = dwg_to_dxf(data)
            if len(converted) > MAX_UPLOAD:
                raise ValueError("Conversion DWG trop volumineuse pour l'import (20 Mio).")
            result = _dxf(converted, doc)
            _warn(result, "DWG converti localement en DXF avant analyse ; vérifier les éléments non convertis dans le dessin original.")
        elif extension in {"xml", "graphml", "drawio"}:
            root = _xml(data)
            if _local(root.tag) == "graphml":
                result = _graphml(root, doc)
            elif extension == "drawio" or _local(root.tag) == "mxfile":
                element = next((element for element in root.iter() if element.get("id") == "fat-studio-pid" and element.get("pid")), None)
                if element is None:
                    raise ValueError("Draw.io : seules les données P&ID natives incorporées sont prises en charge.")
                result = _native(_json(element.get("pid")))
            else:
                result = _dexpi(root, doc)
        elif extension in {"csv", "tsv"}:
            result = _csv(data, doc)
        elif extension == "zip":
            result = _archive(data)
        else:
            raise ValueError("Format P&ID non pris en charge : PDF, images, SVG, DXF, DWG, JSON, GraphML, XML DEXPI ou CSV attendus.")
        result.source_name = name
        result.source_format = extension
        result.source_sha256 = hashlib.sha256(data).hexdigest()
        return _fit_document(_validate(result))
    except ValidationError as exc:
        raise ValueError(f"Données P&ID hors limites : {exc.errors()[0]['msg']}.") from exc
    except (OverflowError, RecursionError, MemoryError) as exc:
        raise ValueError("P&ID trop complexe pour l'import local.") from exc
