"""Second-opinion OCR, used as a cross-check on Tesseract.

Tesseract reads the page first. RapidOCR (PaddleOCR models on ONNX runtime; the models ship inside the pip
wheel, so it runs fully offline) reads it again, and both go through the same label-anchored parser and
validator. Any field where the two engines read something different gets a review flag. In the bake-off this
cut wrong-and-silent fields to 0 (see qa/accuracy-trend.md) because the engines rarely make the same mistake.

The first engine's values are what the reviewer sees. This module only ADDS flags; it never changes a value.

    USREPORT_CROSSCHECK=0   turn it off (faster, but silent errors become possible again)
"""
import logging
import os

import numpy as np

log = logging.getLogger("usreport.crosscheck")

_engine = None


def enabled():
    return os.environ.get("USREPORT_CROSSCHECK", "1") != "0"


def _load():
    """The RapidOCR engine, created once. Raises ImportError if no RapidOCR package is installed."""
    global _engine
    if _engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR as R  # v1: Python < 3.13
            _engine = ("v1", R())
        except ImportError:
            from rapidocr import RapidOCR as R  # v3
            _engine = ("v3", R())
    return _engine


def unavailable():
    """None when the second engine can run, else a short reason."""
    try:
        _load()
    except ImportError:
        return "RapidOCR is not installed (pip install rapidocr-onnxruntime)"
    except Exception as e:  # a broken onnxruntime install, for instance
        return f"RapidOCR failed to start ({type(e).__name__})"
    return None


def split_words(text, x0, x1, cy, h, conf):
    """One detected text line with a box -> word dicts, x positions spread by character offset."""
    total, pos, out = max(len(text), 1), 0, []
    for tok in text.split():
        i = text.index(tok, pos)
        pos = i + len(tok)
        out.append(dict(t=tok, x=x0 + (x1 - x0) * i / total, w=(x1 - x0) * len(tok) / total, cy=cy, h=h, conf=conf))
    return out


def poly_words(items):
    """items: (text, polygon points, confidence 0-1) -> word dicts."""
    words = []
    for text, pts, conf in items:
        p = np.asarray(pts, dtype=float).reshape(-1, 2)
        x0, y0, x1, y1 = p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max()
        words += split_words(str(text), x0, x1, (y0 + y1) / 2, y1 - y0, float(conf) * 100)
    return words


def words(img):
    """RapidOCR on a PIL image -> word dicts for `extract.group_words`."""
    ver, eng = _load()
    arr = np.asarray(img.convert("RGB"))[:, :, ::-1]  # BGR
    if ver == "v1":
        res, _ = eng(arr)
        return poly_words([(t, box, float(s)) for box, t, s in (res or [])])
    out = eng(arr)
    if out.boxes is None:
        return []
    return poly_words(list(zip(out.txts, out.boxes, out.scores)))


def read(img):
    """Full result dict (same shape as `extract.extract`) from the second engine alone."""
    from . import extract as ex
    return ex.extract_lines([ex.group_words(words(img))])


def _show(v):
    return "not read" if v is None else f"{v:g}"


def flag_disagreements(first, second):
    """Add a warning to every slot where the engines read different values. Returns the slot letters flagged.
    Exact comparison, as in the bake-off: both values come from the same parser, so equal text is equal floats."""
    from .schema import SLOTS
    flagged = []
    for s in SLOTS:
        a, b = first["values"].get(s.key), second["values"].get(s.key)
        if a == b:
            continue
        msg = f"second OCR engine disagrees ({_show(b)} vs {_show(a)} read first)"
        first["issues"].setdefault(s.letter, []).append({"level": "warn", "msg": msg})
        flagged.append(s.letter)
    return flagged


def apply(first, img):
    """Cross-check `first` (a Tesseract result) against RapidOCR; sets first["crosscheck"].

    status: "ok" (ran; `disagree` lists flagged slot letters), "off" (disabled), or "unavailable" / "error"
    (could not run: the page is then checked by Tesseract alone, and the UI should say so)."""
    if not enabled():
        first["crosscheck"] = dict(status="off", disagree=[])
        return first
    why = unavailable()
    if why:
        log.warning("cross-check unavailable: %s", why)
        first["crosscheck"] = dict(status="unavailable", reason=why, disagree=[])
        return first
    try:
        second = read(img)
    except Exception as e:  # never let the second opinion break the first
        log.error("cross-check failed: %s", type(e).__name__)
        first["crosscheck"] = dict(status="error", reason=type(e).__name__, disagree=[])
        return first
    first["crosscheck"] = dict(status="ok", disagree=flag_disagreements(first, second))
    return first
