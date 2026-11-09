"""Published Hadlock-family formulas (cm in, weeks / grams out).

Used two ways: to generate realistic synthetic reports, and to cross-check OCR
output. Verified against a real report: BPD 45.04 mm -> 19w4d, AC 147.83 mm ->
20w0d, FL 30.18 mm -> 19w2d, and EFW 308 g from AC/BPD/FL/HC.
"""
import math


def ga_bpd(cm):
    return 9.54 + 1.482 * cm + 0.1676 * cm**2


def ga_hc(cm):
    return 8.96 + 0.540 * cm + 0.0003 * cm**3


def ga_ac(cm):
    return 8.14 + 0.753 * cm + 0.0036 * cm**2


def ga_fl(cm):
    return 10.35 + 2.460 * cm + 0.170 * cm**2


def efw_grams(ac_cm, bpd_cm, fl_cm, hc_cm):
    log10 = (
        1.3596
        - 0.00386 * ac_cm * fl_cm
        + 0.0064 * hc_cm
        + 0.00061 * bpd_cm * ac_cm
        + 0.0424 * ac_cm
        + 0.174 * fl_cm
    )
    return 10**log10


# HL (Jeanty) and transcerebellar (Hill) are approximated; the validator uses
# wider tolerances for them.
def ga_hl(cm):
    return ga_fl(cm * 0.985)


def ga_tcd(cm):
    return cm * 10.0  # ~1 mm per week in the 15-25 wk range


GA_FUNCS = {"bpd": ga_bpd, "hc": ga_hc, "ac": ga_ac, "fl": ga_fl, "hl": ga_hl, "tcd": ga_tcd}


def weeks_to_wd(weeks):
    days = round(weeks * 7)
    return days // 7, days % 7


def invert(func, target_weeks, lo=0.5, hi=12.0):
    """Measurement (cm) whose GA equals target_weeks, by bisection."""
    for _ in range(60):
        mid = (lo + hi) / 2
        if func(mid) < target_weeks:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def fmt_wd(w, d):
    return f"{w}w{d}d"
