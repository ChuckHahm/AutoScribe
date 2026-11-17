"""Failure cases: a page the app misread, kept locally so the errors can be analysed.

A case is a folder under `<data>/failures/` holding `image.png` (the page as the app received it,
lossless) and `case.json` (what OCR read, what the reviewer approved, what was flagged, the raw OCR lines).

PHI: the image and values ARE patient data. They stay in the gitignored `data/` folder on this machine.
Capture is OFF unless `USREPORT_CAPTURE_FAILURES=1`, because storing page images on a clinical machine
is a compliance decision, not a default. Logs never carry values, only slot letters and counts.
"""
import json
import time
from pathlib import Path

from PIL import Image

from .schema import SLOTS
from .version import BUILD_DATE


def num(v):
    """UI/JSON value -> float, or None when blank or not a number."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def clean(values):
    return {s.key: num((values or {}).get(s.key)) for s in SLOTS}


def wrong_slots(read, truth):
    """Letters of slots where the read value differs from what the reviewer approved.
    Same tolerance as extract.compare (0.06 for mm/percent, exact otherwise). A slot OCR read but the
    reviewer blanked counts as wrong (an invented value); both blank is fine."""
    out = []
    for s in SLOTS:
        r, t = read.get(s.key), truth.get(s.key)
        if r is None and t is None:
            continue
        if r is None or t is None or abs(r - t) > (0.06 if s.kind in ("mm", "percent") else 0):
            out.append(s.letter)
    return out


def save(root, img: Image.Image, result: dict, approved: dict, sid="manual", source="reviewer"):
    """Write a case if any slot the reviewer approved differs from what OCR read. Returns the folder or None."""
    read, truth = clean(result["values"]), clean(approved)
    wrong = wrong_slots(read, truth)
    if not wrong:
        return None
    flagged = sorted(set(result["issues"]) | set(result["low_conf"]))
    folder = Path(root) / "failures" / f"{time.strftime('%Y%m%d-%H%M%S')}-{sid}"
    folder.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(folder / "image.png")
    case = dict(t=int(time.time()), build_date=BUILD_DATE, source=source, image="image.png", image_size=list(img.size),
                wrong=wrong, flagged=flagged, silent=[w for w in wrong if w not in flagged],
                read=read, truth=truth, psm=result.get("psm"), ocr_lines=result.get("lines", []),
                issues={k: [i["msg"] for i in v] for k, v in result["issues"].items()})
    (folder / "case.json").write_text(json.dumps(case, indent=1), encoding="utf-8")
    return folder


def load_all(root):
    """[(folder, case dict)] oldest first."""
    out = []
    for f in sorted((Path(root) / "failures").glob("*/case.json")) if (Path(root) / "failures").exists() else []:
        try:
            out.append((f.parent, json.loads(f.read_text(encoding="utf-8"))))
        except ValueError:
            continue
    return out
