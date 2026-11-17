"""Where do the misreads come from? Re-runs the CURRENT OCR on every saved failure case and sorts the
wrong fields by kind. Prints counts and slot letters only (no values), so the output is safe to share.

    PYTHONPATH=src python tools/failure_report.py [--data DIR] [--show-values]

Kinds: unread | extra_value (reviewer blanked what OCR read) | decimal_or_unit (off by 10x/100x) | digit_sub (one digit wrong, with the confusion pair)
       | digit_dropped | digit_extra | other_slot_value (read equals another slot's true value: row shift)
       | other.
--show-values prints real values too. That is patient data: only use it on your own screen.
"""
import argparse
import os
from collections import Counter
from pathlib import Path

from PIL import Image

from usreport import failures
from usreport.extract import extract
from usreport.schema import SLOT_BY_KEY, SLOTS


def digits(v):
    return f"{v:g}".replace(".", "").replace("-", "")


def classify(key, read, truth):
    """(kind, detail) for one wrong field. `truth` is the full {key: value} dict of the case."""
    t = truth[key]
    if t is None:
        return "extra_value", ""  # OCR produced a value; the reviewer cleared it
    if read is None:
        return "unread", ""
    if t and read and any(abs(read / t - f) < 0.01 * f for f in (10, 100, 0.1, 0.01)):
        return "decimal_or_unit", ""
    a, b = digits(t), digits(read)
    if len(a) == len(b):
        diff = [(x, y) for x, y in zip(a, b) if x != y]
        if len(diff) == 1:
            return "digit_sub", f"{diff[0][0]}>{diff[0][1]}"
    if len(b) == len(a) - 1 and any(a[:i] + a[i + 1:] == b for i in range(len(a))):
        return "digit_dropped", ""
    if len(b) == len(a) + 1 and any(b[:i] + b[i + 1:] == a for i in range(len(b))):
        return "digit_extra", ""
    sl = SLOT_BY_KEY[key]
    if sl.kind in ("mm", "grams", "percent") and any(
            k != key and v is not None and SLOT_BY_KEY[k].kind == sl.kind and abs(v - read) < 0.06 for k, v in truth.items()):
        return "other_slot_value", ""
    return "other", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.environ.get("DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
    ap.add_argument("--show-values", action="store_true")
    a = ap.parse_args()
    cases = failures.load_all(a.data)
    if not cases:
        raise SystemExit(f"no failure cases under {a.data}/failures (set USREPORT_CAPTURE_FAILURES=1, or tools/add_failure.py)")
    kinds, by_slot, pairs = Counter(), Counter(), Counter()
    n_wrong = n_silent = n_wrong_then = n_silent_then = fixed = 0
    for folder, c in cases:
        img = Image.open(folder / c["image"])
        img.load()
        r = extract(img)
        read, truth = failures.clean(r["values"]), c["truth"]
        wrong = failures.wrong_slots(read, truth)
        flagged = set(r["issues"]) | set(r["low_conf"])
        n_wrong_then += len(c["wrong"]); n_silent_then += len(c["silent"])
        fixed += len(set(c["wrong"]) - set(wrong))
        n_wrong += len(wrong); n_silent += sum(w not in flagged for w in wrong)
        for letter in wrong:
            key = next(s.key for s in SLOTS if s.letter == letter)
            kind, detail = classify(key, read[key], truth)
            kinds[kind] += 1; by_slot[(letter, letter in flagged)] += 1
            if detail:
                pairs[detail] += 1
            if a.show_values:
                print(f"  {folder.name} {letter}: read {read[key]} true {truth[key]} -> {kind} {detail} {'flagged' if letter in flagged else 'SILENT'}")
    print(f"{len(cases)} case(s), {len(set(c['build_date'] for _, c in cases))} build date(s) at capture\n")
    print(f"at capture time : {n_wrong_then} wrong fields, {n_silent_then} unflagged (silent)")
    print(f"current OCR now : {n_wrong} wrong fields, {n_silent} unflagged (silent); {fixed} fixed since capture\n")
    print("by kind (current OCR):")
    for k, n in kinds.most_common():
        print(f"  {k:18} {n}")
    if pairs:
        print("\ndigit confusions (true>read): " + ", ".join(f"{p} x{n}" for p, n in pairs.most_common()))
    print("\nby slot (wrong / of which silent):")
    for letter in sorted({l for l, _ in by_slot}):
        fl, si = by_slot[(letter, True)], by_slot[(letter, False)]
        print(f"  {letter} ({next(s.label for s in SLOTS if s.letter == letter)}): {fl + si} / {si}")


if __name__ == "__main__":
    main()
