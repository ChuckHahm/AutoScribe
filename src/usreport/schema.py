"""Epic MFM anatomy-scan template: the 23 fill-in slots (A-W) in tab order.

Mirrors the labeled screenshots, which carry the same red letter on both sides of the mapping:
`IMG_5701 START with LABELED DATA FIELDS.png` (GE sonogram, input) and
`IMG_5706 END with LABELED DATA FIELDS.png` (Epic, output). `source` names the GE field.
Ages print as `WWwDDd` (e.g. "19w4d"); "w" and "d" are delimiters, and Epic takes the
week and day numbers in separate slots.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Slot:
    letter: str
    key: str
    label: str
    kind: str  # mm | weeks | days | grams | percent
    source: str = ""  # where the value is read on the GE sonogram


def _measure(start, key, name):
    a = ord(start)
    return [
        Slot(chr(a), f"{key}_mm", f"{name} (mm)", "mm", f"{name} row, Value column"),
        Slot(chr(a + 1), f"{key}_w", f"{name} GA weeks", "weeks", f"{name} row, Age column (WW of WWwDDd)"),
        Slot(chr(a + 2), f"{key}_d", f"{name} GA days", "days", f"{name} row, Age column (DD of WWwDDd)"),
    ]


SLOTS = (
    _measure("A", "bpd", "BPD")
    + _measure("D", "hc", "HC")
    + _measure("G", "ac", "AC")
    + _measure("J", "fl", "FL")
    + _measure("M", "hl", "HL")
    + _measure("P", "tcd", "Transcerebellar")
    + [
        Slot("S", "us_w", "Ultrasound age weeks", "weeks", "GA(AUA) field (WW of WWwDDd)"),
        Slot("T", "us_d", "Ultrasound age days", "days", "GA(AUA) field (DD of WWwDDd)"),
        Slot("U", "efw_g", "EFW (grams)", "grams", "EFW row, Value column"),
        Slot("V", "efw_pct", "EFW percentile", "percent", "EFW row, GP column"),
        Slot("W", "ac_pct", "AC percentile", "percent", "AC row, GP column"),
    ]
)

SLOT_BY_KEY = {s.key: s for s in SLOTS}
SLOT_BY_LETTER = {s.letter: s for s in SLOTS}

# GE report rows -> measurement key
MEASUREMENTS = ("bpd", "hc", "ac", "fl", "hl", "tcd")
