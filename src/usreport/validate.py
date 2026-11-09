"""Cross-checks on an extracted record. The reviewer still approves everything;
these flags tell her where to look first."""
from . import hadlock
from .schema import MEASUREMENTS, SLOT_BY_KEY, SLOTS

# Broad physiologic bounds (mm) for a mid-trimester anatomy scan, ~14-32 weeks.
MM_RANGE = {
    "bpd": (25, 90), "hc": (90, 320), "ac": (80, 330),
    "fl": (12, 70), "hl": (12, 65), "tcd": (12, 40),
}
GA_TOL_DAYS = {"bpd": 4, "hc": 4, "ac": 4, "fl": 4, "hl": 10, "tcd": 10}


def _safe(fn, *args):
    """Cross-checks run on possibly garbage OCR numbers; never let them raise."""
    try:
        return fn(*args)
    except (OverflowError, ValueError, ZeroDivisionError):
        return None


def _plausible(m, mm):
    lo, hi = MM_RANGE[m]
    return mm is not None and lo <= mm <= hi


def _issue(issues, key, level, msg):
    issues.setdefault(SLOT_BY_KEY[key].letter, []).append({"level": level, "msg": msg})


def validate(values, repeats=None):
    """values: {slot_key: number}; repeats: {meas: [value_mm, m1, m2, m3]} or None.

    Returns {slot_letter: [{level, msg}]}. Level is 'error' or 'warn'.
    """
    issues = {}
    ga4 = [values.get(f"{m}_{x}") for m in ("bpd", "hc", "ac", "fl") for x in ("w", "d")]
    hint = ""
    if None not in ga4:  # suggestion only; never auto-filled
        mean = sum(ga4[i] * 7 + ga4[i + 1] for i in range(0, 8, 2)) / 4
        hint = f" (suggestion, not read: ~{hadlock.fmt_wd(*hadlock.weeks_to_wd(mean / 7))} from BPD/HC/AC/FL ages)"
    for slot in SLOTS:
        if values.get(slot.key) is None:
            _issue(issues, slot.key, "error", "not found" + (hint if slot.key in ("us_w", "us_d") else ""))

    for m in MEASUREMENTS:
        mm, w, d = values.get(f"{m}_mm"), values.get(f"{m}_w"), values.get(f"{m}_d")
        if mm is not None:
            lo, hi = MM_RANGE[m]
            if not lo <= mm <= hi:
                _issue(issues, f"{m}_mm", "error", f"{mm} mm outside {lo}-{hi} (unit mix-up?)")
        if w is not None and not 10 <= w <= 42:
            _issue(issues, f"{m}_w", "error", f"{w} weeks implausible")
        if d is not None and not 0 <= d <= 6:
            _issue(issues, f"{m}_d", "error", f"{d} days must be 0-6")
        if None not in (mm, w, d) and _plausible(m, mm):
            expect = hadlock.GA_FUNCS[m](mm / 10.0) * 7
            got = w * 7 + d
            if abs(expect - got) > GA_TOL_DAYS[m]:
                msg = f"GA {w}w{d}d vs ~{hadlock.fmt_wd(*hadlock.weeks_to_wd(expect / 7))} expected from size"
                for sfx in ("mm", "w", "d"):  # which of the three is wrong is unknown: flag the whole row
                    _issue(issues, f"{m}_{sfx}", "warn", msg)

    if repeats:
        for m, vals in repeats.items():
            if vals and len(vals) >= 3 and vals[0] is not None:
                reps = [v for v in vals[1:] if v is not None]
                if reps and abs(sum(reps) / len(reps) - vals[0]) > 0.06:
                    _issue(issues, f"{m}_mm", "warn", f"value {vals[0]} != average of repeats {reps}")

    four = [values.get(f"{m}_w") is not None and values.get(f"{m}_d") is not None for m in ("bpd", "hc", "ac", "fl")]
    us_w, us_d = values.get("us_w"), values.get("us_d")
    if all(four) and us_w is not None and us_d is not None:
        mean = sum(values[f"{m}_w"] * 7 + values[f"{m}_d"] for m in ("bpd", "hc", "ac", "fl")) / 4
        if abs(mean - (us_w * 7 + us_d)) > 3:
            _issue(issues, "us_w", "warn", "ultrasound age differs from mean of BPD/HC/AC/FL ages")

    needed = [values.get(k) for k in ("ac_mm", "bpd_mm", "fl_mm", "hc_mm")]
    ok_sizes = all(_plausible(m, v) for m, v in zip(("ac", "bpd", "fl", "hc"), needed))
    expect = _safe(hadlock.efw_grams, *(v / 10.0 for v in needed)) if ok_sizes else None
    if expect and values.get("efw_g") is not None:
        if abs(expect - values["efw_g"]) / expect > 0.04:
            _issue(issues, "efw_g", "warn", f"EFW {values['efw_g']} g vs ~{expect:.0f} g from AC/BPD/FL/HC")

    for k in ("efw_pct", "ac_pct"):
        v = values.get(k)
        if v is not None and not 0 <= v <= 100:
            _issue(issues, k, "error", f"{v}% out of range")
    return issues
