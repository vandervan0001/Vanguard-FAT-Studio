"""Offline CPU OCR using the models shipped in rapidocr-onnxruntime's wheel."""

from __future__ import annotations

import threading

_LOCK = threading.Lock()
_ENGINE = None


def recognize(image) -> list[tuple[str, float, float, float]]:
    """Return text, image x/y and confidence; never fetch a remote model."""
    global _ENGINE
    try:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise ValueError("OCR local indisponible : installer les dépendances P&ID verrouillées.") from exc
    with _LOCK:
        if _ENGINE is None:
            _ENGINE = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)
        result, _ = _ENGINE(np.asarray(image.convert("RGB")), use_cls=False)
    rows = []
    for box, text, confidence in (result or []):
        if len(rows) >= 10000:
            raise ValueError("OCR trop complexe : plus de 10 000 zones de texte.")
        rows.append((str(text), sum(p[0] for p in box) / len(box),
                     sum(p[1] for p in box) / len(box), float(confidence)))
    return rows
