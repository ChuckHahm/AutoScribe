"""Synthetic GE-style OB measurement report pages with ground truth.

All values are invented. Layout follows the real report (`IMG_5701 START.png`):
header, EFW row, then a 2D-measurement table with value / m1 / m2 / m3 / avg /
percentile / GA. `photo=True` degrades the render to look like a phone photo of
a monitor (tilt, blur, noise, glare, JPEG).
"""
import io
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import hadlock
from .schema import MEASUREMENTS



def _font(size):
    """Use Pillow's embedded font so synthetic pages render identically across platforms."""
    return ImageFont.load_default(size=size)
W, H = 1600, 1200
BG, PANEL, INK, DIM, BOX = (14, 18, 40), (62, 67, 80), (240, 240, 240), (200, 200, 205), (84, 90, 104)

ROWS = [  # key, on-screen label, number of repeat measurements
    ("bpd", "BPD (Hadlock)", 2), ("hc", "HC (Hadlock)", 2), ("ac", "AC (Hadlock)", 2),
    ("fl", "FL (Hadlock)", 2), ("hl", "HL (Jeanty)", 1), ("tcd", "Cereb (Hill)", 1),
]
DISTRACTORS = [("CM", 4.69), ("Vp", 5.93), ("NF", 5.65)]  # rows with no GA, as on the real page


def generate_record(rng, unit="mm"):
    """Return (truth, display). truth: slot values in mm/w/d/g/%; display: strings to render."""
    true_days = rng.uniform(18 * 7, 23 * 7)
    values, repeats, disp = {}, {}, {}
    for key, _, n_rep in ROWS:
        weeks = (true_days + rng.gauss(0, 5)) / 7
        mm = hadlock.invert(hadlock.GA_FUNCS[key], weeks, hi=40) * 10
        reps = [round(mm + rng.gauss(0, 0.4), 2) for _ in range(n_rep)]
        value = round(sum(reps) / len(reps), 2)
        if unit == "cm":  # machine configured in cm: 2 decimals on screen
            reps = [round(r / 10, 2) for r in reps]
            value = round(sum(reps) / len(reps), 2)
            mm_val = round(value * 10, 2)
        else:
            mm_val = value
        w, d = hadlock.weeks_to_wd(hadlock.GA_FUNCS[key](mm_val / 10))
        pct = round(rng.uniform(4, 96), 1)
        values.update({f"{key}_mm": mm_val, f"{key}_w": w, f"{key}_d": d})
        repeats[key] = [mm_val] + [r * (10 if unit == "cm" else 1) for r in reps]
        disp[key] = dict(value=value, reps=reps, pct=pct, ga=hadlock.fmt_wd(w, d))
        if key == "ac":
            values["ac_pct"] = pct
    efw = round(hadlock.efw_grams(*(values[f"{k}_mm"] / 10 for k in ("ac", "bpd", "fl", "hc"))))
    values["efw_g"], values["efw_pct"] = efw, round(rng.uniform(4, 96), 1)
    mean_days = sum(values[f"{k}_w"] * 7 + values[f"{k}_d"] for k in ("bpd", "hc", "ac", "fl")) / 4
    values["us_w"], values["us_d"] = hadlock.weeks_to_wd(mean_days / 7)
    disp["_efw"] = dict(g=efw, oz=round(efw / 28.35), sd=round(efw * 0.146), pct=values["efw_pct"],
                        ga=hadlock.fmt_wd(values["us_w"], values["us_d"]))
    disp["_unit"] = unit
    return {"values": values, "repeats": repeats, "unit": unit}, disp


def render(disp, rng):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f, fb, fs = (_font(17), _font(16), _font(15))
    d.rectangle([310, 262, 1250, 935], fill=PANEL)

    def text(xy, s, font=f, fill=INK):
        d.text(xy, s, font=font, fill=fill, anchor="lm")

    def box(x0, y, w, s, font=f):
        d.rectangle([x0, y - 13, x0 + w, y + 13], outline=(150, 155, 165), fill=BOX)
        text((x0 + 8, y), s, font)

    text((1085, 270), "OB LOW RISK ANATOMY", fb)
    text((900, 300), "SYNTHETIC - NOT A REAL PATIENT", fs, DIM)
    text((405, 423), "Height:", fb); box(485, 423, 100, "160.7 cm")
    text((627, 423), "Weight:", fb); box(705, 423, 95, "78.93 kg")
    text((830, 423), "BMI:", fb); box(868, 423, 55, "30.6")
    text((622, 458), "GA(EDD)", fb); box(702, 458, 100, "20w3d")
    text((862, 458), "EDD", fb); box(905, 458, 105, "03/07/2027")
    text((622, 486), "GA(AUA)", fb); box(702, 486, 100, disp["_efw"]["ga"])
    text((815, 486), "EDD(AUA)", fb); box(905, 486, 105, "03/11/2027")

    e = disp["_efw"]
    text((388, 519), "EFW (Hadlock)", fb)
    for x, s in ((628, "Value"), (755, "Range"), (860, "Age"), (950, "Range")):
        text((x, 519), s, fb)
    box(388, 548, 185, "AC/BPD/FL/HC")
    text((608, 548), f"{e['g']}g ({e['oz']}oz)")
    text((755, 548), f"± {e['sd']}g")
    text((840, 548), e["ga"])
    text((1128, 548), f"{e['pct']}%")

    for x, s in ((388, "2D Measurements"), (560, "AUA"), (603, "Value"), (730, "m1"), (808, "m2"),
                 (885, "m3"), (948, "Meth."), (1055, "GP"), (1165, "Age")):
        text((x, 583), s, fb)
    unit = disp["_unit"]
    y = 617
    for key, label, n_rep in ROWS:
        r = disp[key]
        text((393, y), label, fb)
        d.rectangle([563, y - 6, 575, y + 6], outline=INK)
        text((600, y), f"{r['value']:.2f} {unit}")
        for i, x in enumerate((706, 786, 866)):
            d.rectangle([x, y - 13, x + 76, y + 13], outline=(150, 155, 165), fill=BOX)
            if i < len(r["reps"]):
                text((x + 18, y), f"{r['reps'][i]:.2f}")
        d.rectangle([944, y - 12, 988, y + 12], fill=(200, 200, 205))
        text((952, y), "avg.", fs, (20, 20, 20))
        d.line([1007, y, 1067, y], fill=INK); d.ellipse([1028, y - 3, 1034, y + 3], fill=(240, 220, 60))
        text((1078, y), f"{r['pct']}%")
        text((1160, y), r["ga"])
        y += 27
    for label, v in DISTRACTORS:
        text((393, y), label, fb)
        text((600, y), f"{v:.2f} {unit}")
        d.rectangle([944, y - 12, 988, y + 12], fill=(200, 200, 205))
        y += 27
    return img


def photoify(img, rng, severity=1.0):
    """Degrade a clean render so it resembles a phone photo of a monitor."""
    w, h = img.size
    sv = severity
    dx = lambda: rng.uniform(-0.03, 0.03) * sv * w
    dy = lambda: rng.uniform(-0.03, 0.03) * sv * h
    quad = (dx(), dy(), dx(), h + dy(), w + dx(), h + dy(), w + dx(), dy())
    img = img.transform((w, h), Image.QUAD, quad, Image.BICUBIC, fillcolor=(30, 30, 30))
    img = img.rotate(rng.uniform(-2, 2) * sv, resample=Image.BICUBIC, fillcolor=(30, 30, 30))
    img = img.filter(ImageFilter.GaussianBlur(0.3 + rng.uniform(0.3, 0.9) * sv))
    a = np.asarray(img, dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = rng.uniform(0.2, 0.8) * w, rng.uniform(0.1, 0.5) * h
    glare = 55 * np.exp(-(((xx - cx) / (0.25 * w)) ** 2 + ((yy - cy) / (0.18 * h)) ** 2))
    a = a * rng.uniform(0.8, 1.05) + glare[..., None] + np.random.default_rng(rng.randrange(1 << 30)).normal(0, 7 * sv, a.shape)
    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=rng.randint(90 - int(35 * sv), 95 - int(15 * sv)))
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def make_sample(seed, unit="mm", photo=False, severity=1.0):
    rng = random.Random(seed)
    truth, disp = generate_record(rng, unit)
    img = render(disp, rng)
    if photo:
        img = photoify(img, rng, severity)
    truth.update(seed=seed, photo=photo, severity=severity)
    return img, truth
