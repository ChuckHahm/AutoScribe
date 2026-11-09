"""Image -> Epic slot values, fully offline (Tesseract).

The GE page layout is fixed, so rows are located by their printed label
("BPD (Hadlock)", ...) and values read by pattern, not by pixel position. That
tolerates the tilt and shift of a phone photo. Two Tesseract page-segmentation
modes are tried and the one that validates best wins.
"""
import os
import re
import shutil
import statistics

import cv2
import numpy as np
import pytesseract
from PIL import Image

from .schema import MEASUREMENTS, SLOT_BY_KEY, SLOTS
from .validate import validate

_WIN_TESSERACT = (r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe")


def _find_tesseract():
    """TESSERACT_CMD env var, else PATH, else the default Windows installer location."""
    for c in (os.environ.get("TESSERACT_CMD"), shutil.which("tesseract"), *_WIN_TESSERACT):
        if c and os.path.exists(c):
            return c
    return None


pytesseract.pytesseract.tesseract_cmd = _find_tesseract() or "tesseract"

ROW_RE = re.compile(r"^\W*(BPD|HC|AC|FL|HL|C[EO]R[EO][BD8])(?![/\w])", re.I)
ROW_KEY = {"BPD": "bpd", "HC": "hc", "AC": "ac", "FL": "fl", "HL": "hl"}
VALUE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*[^\w\s]?\s*(mm|cm)", re.I)  # junk may sit before or after the unit (e.g. "mm__", "mmi")
NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
DEC_RE = re.compile(r"\d+[.,]\d+")
PCT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
AGE = r"(\d[\dOo]?)\s*[wW]\s*([0-6]|[A-Za-z\u00c0-\u017f$|!]{1,2})\s*[dD]"  # day digit is often misread as a letter
AGE_RE = re.compile(AGE)
AUA_RE = re.compile(r"AUA\)?[^\w]{0,4}\s*" + AGE)  # box borders can sit between label and value
EFW_RE = re.compile(r"(\d{2,4})\s*g\s*\(")


LOW_CONF = 40  # a row whose value words average below this is flagged. Confidence is a weak signal here (wrong rows
# were mostly caught by validate(), and one slipped through at 75), so this only catches truly unreadable rows.


def _f(s):
    return float(s.replace(",", "."))


def _data_conf(line):
    """Mean Tesseract confidence of the words that carry data (those with a digit).

    The rest of a row (checkbox, "avg." button, GP slider, box borders) is noise to Tesseract and
    says nothing about whether the numbers were read right, so it is left out.
    """
    cs = [w["conf"] for w in line["words"] if any(c.isdigit() for c in w["t"])]
    return statistics.fmean(cs) if cs else line["conf"]


_DAY_FIX = {**{c: 1 for c in "Il|!i"}, **{c: 0 for c in "Oo"}, **{c: 5 for c in "Ss$"},
            **{c: 6 for c in "\u00e9\u00e8\u00ea\u00ebeEbGg"}, "A": 4}


def _wk(tok):
    return int(tok.replace("O", "0").replace("o", "0"))


def _day(tok):
    """Day digit 0-6 from an OCR token, or None if ambiguous/impossible."""
    if tok.isdigit():
        return int(tok)
    digits = {_DAY_FIX.get(c) for c in tok}
    return digits.pop() if len(digits) == 1 and None not in digits else None


def _pct(raw):
    """GE prints percentiles with 1 decimal; '316' means 31.6 (flagged)."""
    if "." not in raw and "," not in raw and len(raw) == 3 and int(raw) > 100:
        return int(raw) / 10, True
    return _f(raw), False


def _num(raw):
    """Parse a measurement. GE always prints 2 decimals, so '2068' means 20.68 (flagged)."""
    if "." in raw or "," in raw:
        return _f(raw), False
    if len(raw) >= 3:
        return int(raw) / 100, True
    return float(raw), False


def _deskew(bw):
    """Rotate so text rows are horizontal (projection-profile search, +-5 deg)."""
    small = 255 - cv2.resize(bw, None, fx=0.4, fy=0.4, interpolation=cv2.INTER_AREA)
    h, w = small.shape
    best_var, best_ang = -1.0, 0.0
    for ang in np.arange(-5, 5.01, 0.25):
        m = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1)
        rows = cv2.warpAffine(small, m, (w, h), flags=cv2.INTER_NEAREST).sum(axis=1, dtype=np.float64)
        if rows.var() > best_var:
            best_var, best_ang = rows.var(), ang
    m = cv2.getRotationMatrix2D((bw.shape[1] / 2, bw.shape[0] / 2), best_ang, 1)
    return cv2.warpAffine(bw, m, (bw.shape[1], bw.shape[0]), flags=cv2.INTER_LINEAR, borderValue=255)


def preprocess(img):
    """Grayscale -> normalize size -> adaptive threshold (dark text on white) -> deskew.

    Adaptive thresholding is what makes Tesseract work here: the report is light text on
    a mid-gray panel inside a dark border, and uneven glare is common in photos.
    """
    g = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
    scale = min(3.0, max(0.5, 2400 / g.shape[1]))
    g = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    if g.mean() < 110:
        g = 255 - g  # dark theme -> dark text on light
    bw = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 10)
    return Image.fromarray(_deskew(bw))


def ocr_lines(img, psm):
    d = pytesseract.image_to_data(img, config=f"--psm {psm}", output_type=pytesseract.Output.DICT)
    words = [
        dict(t=d["text"][i], x=d["left"][i], w=d["width"][i], cy=d["top"][i] + d["height"][i] / 2, h=d["height"][i],
             conf=float(d["conf"][i]))
        for i in range(len(d["text"])) if d["text"][i].strip() and float(d["conf"][i]) >= 0
    ]
    if not words:
        return []
    tol = 0.6 * statistics.median(w["h"] for w in words)
    words.sort(key=lambda w: w["cy"])
    lines, cur = [], [words[0]]
    for w in words[1:]:
        if abs(w["cy"] - statistics.fmean(c["cy"] for c in cur)) <= tol:
            cur.append(w)
        else:
            lines.append(cur); cur = [w]
    lines.append(cur)
    return [
        dict(text=" ".join(w["t"] for w in sorted(l, key=lambda w: w["x"])),
             conf=statistics.fmean(w["conf"] for w in l), words=sorted(l, key=lambda w: w["x"]))
        for l in lines
    ]


def read_aua(pre, lines):
    """GA(AUA) sits in a bordered box that confuses Tesseract. Crop right of its label,
    erase the box lines, and read just that field."""
    arr = np.asarray(pre)
    med_h = statistics.median(w["h"] for l in lines for w in l["words"])
    for line in lines:
        for i, w in enumerate(line["words"]):
            t = w["t"].upper()
            if "AUA" in t and not t.startswith("EDD") and t.startswith("G"):
                x0 = w["x"] + w["w"]
                nxt = [v["x"] for v in line["words"][i + 1:] if "EDD" in v["t"].upper()]
                x1 = min(nxt) if nxt else x0 + int(10 * med_h)
                y0, y1 = int(w["cy"] - 0.7 * med_h), int(w["cy"] + 0.7 * med_h)  # stay within this row
                crop = arr[max(y0, 0):y1, x0:x1]
                if crop.size == 0:
                    continue
                inv = 255 - crop
                # erase only full-height strokes (the box border), never digit stems
                borders = cv2.morphologyEx(
                    inv, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(10, int(0.9 * crop.shape[0])))))
                clean = cv2.copyMakeBorder(255 - cv2.subtract(inv, borders), 20, 20, 20, 20,
                                           cv2.BORDER_CONSTANT, value=255)
                txt = pytesseract.image_to_string(
                    Image.fromarray(clean), config="--psm 7 -c tessedit_char_whitelist=0123456789wWdD")
                a = AGE_RE.search(txt)
                if a and _day(a.group(2)) is not None:
                    return _wk(a.group(1)), _day(a.group(2))
    return None


def parse(lines):
    values = {s.key: None for s in SLOTS}
    repeats, conf, notes = {}, {}, {}
    for line in lines:
        text = line["text"]
        m = ROW_RE.match(text)
        if m:
            key = ROW_KEY.get(m.group(1).upper(), "tcd")  # Cereb(ellar), however OCR spells it
            rest = text[m.end():]
            v = VALUE_RE.search(rest)
            if not v:
                continue
            val, fixed = _num(v.group(1))
            if fixed:
                notes[f"{key}_mm"] = "decimal point missing in OCR; inferred"
            unit = v.group(2).lower()
            k = 10.0 if unit == "cm" else 1.0
            after = rest[v.end():]
            pct = PCT_RE.search(after)
            seg = after[:pct.start()] if pct else after
            reps = [round(_f(x) * k, 2) for x in DEC_RE.findall(seg)]
            values[f"{key}_mm"] = round(val * k, 2)
            repeats[key] = [values[f"{key}_mm"]] + reps
            if pct:
                p, fixed = _pct(pct.group(1))
                if key == "ac":
                    values["ac_pct"] = p
                    if fixed:
                        notes["ac_pct"] = "percentile decimal missing in OCR; inferred"
                age = AGE_RE.search(after[pct.end():])
            else:
                age = AGE_RE.search(after)
            if age and _day(age.group(2)) is not None:
                values[f"{key}_w"], values[f"{key}_d"] = _wk(age.group(1)), _day(age.group(2))
            conf[key] = _data_conf(line)
            continue
        e = EFW_RE.search(text)
        if e and values["efw_g"] is None:
            values["efw_g"] = int(e.group(1))
            p = PCT_RE.search(text[e.end():])
            if p:
                values["efw_pct"], fixed = _pct(p.group(1))
                if fixed:
                    notes["efw_pct"] = "percentile decimal missing in OCR; inferred"
            conf["efw"] = _data_conf(line)
        a = AUA_RE.search(text)
        if a and values["us_w"] is None and _day(a.group(2)) is not None:
            values["us_w"], values["us_d"] = _wk(a.group(1)), _day(a.group(2))
    return values, repeats, conf, notes


def _score(values, issues):
    errs = sum(1 for v in issues.values() for i in v if i["level"] == "error" and not i["msg"].startswith("not found"))
    warns = sum(1 for v in issues.values() for i in v if i["level"] == "warn")
    return sum(v is not None for v in values.values()) - 2 * errs - warns


def extract(img: Image.Image):
    """Return {values, repeats, issues, low_conf, psm, lines}.

    Runs two Tesseract modes, takes the best-validating one, then fills fields it missed
    from the other. Everything is re-validated afterwards.
    """
    pre = preprocess(img)
    runs = []
    for psm in (6, 11):
        lines = ocr_lines(pre, psm)
        values, repeats, conf, notes = parse(lines)
        if values["us_w"] is None:
            aua = read_aua(pre, lines)
            if aua:
                values["us_w"], values["us_d"] = aua
        runs.append((_score(values, validate(values, repeats)), psm, values, repeats, conf, lines, notes))
    runs.sort(key=lambda r: -r[0])
    _, psm, values, repeats, conf, lines, notes = runs[0]
    values, repeats, conf, notes = dict(values), dict(repeats), dict(conf), dict(notes)
    for _, _, v2, r2, c2, _, _ in runs[1:]:
        for k, v in v2.items():  # both modes read it, differently: a bad read in at least one
            if v is not None and values[k] is not None and abs(v - values[k]) > 1e-6:
                notes.setdefault(k, f"OCR modes disagree ({values[k]:g} vs {v:g})")
        for m in MEASUREMENTS:  # fill a whole row from the other run only if this run lost it
            if values[f"{m}_mm"] is None and v2[f"{m}_mm"] is not None:
                for sfx in ("mm", "w", "d"):
                    values[f"{m}_{sfx}"] = v2[f"{m}_{sfx}"]
                repeats[m], conf[m] = r2.get(m), c2.get(m, 0)
        for k in ("ac_pct", "efw_g", "efw_pct", "us_w", "us_d"):
            if values[k] is None and v2[k] is not None:
                values[k] = v2[k]
    issues = validate(values, repeats)
    for k, msg in notes.items():
        issues.setdefault(SLOT_BY_KEY[k].letter, []).append({"level": "warn", "msg": msg})
    low = sorted({s.letter for s in SLOTS for m in MEASUREMENTS
                  if s.key.startswith(m + "_") and conf.get(m, 100) < LOW_CONF})
    return dict(values=values, repeats=repeats, issues=issues, low_conf=low, conf=conf, psm=psm,
                lines=[l["text"] for l in lines])


def compare(values, truth):
    """Per-slot exact-match vs ground truth (numbers within 0.06 for mm/percent)."""
    ok = {}
    for s in SLOTS:
        a, b = values.get(s.key), truth.get(s.key)
        ok[s.key] = a is not None and abs(a - b) <= (0.06 if s.kind in ("mm", "percent") else 0)
    return ok
