"""Two-engine OCR: RapidOCR reads the page, Tesseract checks it.

RapidOCR (PaddleOCR models on ONNX runtime; the models ship inside the pip wheel, so it runs fully offline)
was the more accurate engine in the bake-off (qa/accuracy-trend.md), so its values are what the reviewer sees.
Tesseract reads the page independently, both go through the same label-anchored parser and validator, and any
field where the two read something different gets a review flag. Two different engines rarely make the same
mistake, which is what keeps wrong-and-silent fields near zero. This module only ADDS flags; it never changes
a value, and never fills a box from the other engine.

    USREPORT_CROSSCHECK=0   Tesseract alone (faster, but silent errors become possible again)
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
    return "nothing" if v is None else f"{v:g}"


def flag_disagreements(first, second):
    """Add a warning to every slot where the engines read different values. Returns the slot letters flagged.
    Exact comparison, as in the bake-off: both values come from the same parser, so equal text is equal floats."""
    from .schema import SLOTS
    flagged = []
    for s in SLOTS:
        a, b = first["values"].get(s.key), second["values"].get(s.key)
        if a == b:
            continue
        msg = f"second OCR engine disagrees: it read {_show(b)}, the first read {_show(a)}"
        first["issues"].setdefault(s.letter, []).append({"level": "warn", "msg": msg})
        flagged.append(s.letter)
    return flagged


def run(img, tesseract):
    """Read `img` with RapidOCR (the values the reviewer sees) and with Tesseract (the independent check), and
    flag every slot where they differ. `tesseract` is a callable img -> result dict.

    result["crosscheck"] = dict(status, primary, disagree):
      status "ok"          both engines ran; `disagree` lists the flagged slot letters
      status "off"         disabled by USREPORT_CROSSCHECK=0: Tesseract alone
      status "unavailable" RapidOCR is missing or broke on startup: Tesseract alone
      status "error"       one engine failed on this page: the other engine's values, no check
    Whenever the check did not run, the UI tells the reviewer to check every value."""
    if not enabled():
        first = tesseract(img)
        first["crosscheck"] = dict(status="off", primary="tesseract", disagree=[])
        return first
    why = unavailable()
    if why:
        log.warning("RapidOCR unavailable, using Tesseract alone: %s", why)
        first = tesseract(img)
        first["crosscheck"] = dict(status="unavailable", primary="tesseract", reason=why, disagree=[])
        return first
    try:
        first = read(img)
    except Exception as e:  # RapidOCR failed on this page: fall back to Tesseract alone
        log.error("RapidOCR failed: %s; using Tesseract alone", type(e).__name__)
        first = tesseract(img)
        first["crosscheck"] = dict(status="error", primary="tesseract", reason=type(e).__name__, disagree=[])
        return first
    try:
        second = tesseract(img)
    except Exception as e:  # never let the check break the read
        log.error("Tesseract check failed: %s", type(e).__name__)
        first["crosscheck"] = dict(status="error", primary="rapidocr", reason=type(e).__name__, disagree=[])
        return first
    first["crosscheck"] = dict(status="ok", primary="rapidocr", disagree=flag_disagreements(first, second))
    return first
