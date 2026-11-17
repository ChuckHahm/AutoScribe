"""Which OCR engine misreads least, and which misreads are SILENT (wrong and unflagged)?

Every engine's text goes through the same parser and validator, so only recognition differs.
Datasets: fresh synthetic pages (clean mm, clean cm, phone photo of a screen) and, with --failures,
the real misreads saved under data/failures/. Real-case output is counts only (no values).

    PYTHONPATH=src python tools/bakeoff.py [-n 20] [--engines tess_current,tess_noblur,...] [--failures] [--md]

The "A+B" rows take tess_current's values but flag any field where engine B reads something different:
what you would get by running a second engine as a cross-check. Compare SILENT, then false alarms.
Log the run in qa/accuracy-trend.md (--md prints a row). A page that no engine reads is no verdict
on the engines; look at the page.
"""
import argparse
import os
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import ocr_engines  # noqa: E402
from usreport import failures  # noqa: E402
from usreport.extract import compare  # noqa: E402
from usreport.schema import SLOTS  # noqa: E402
from usreport.synth import make_sample  # noqa: E402

BASE = "tess_current"


SYNTH = (("synth clean mm", "mm", False, 0), ("synth clean cm", "cm", False, 0), ("synth photo mm sev 0.6", "mm", True, 0.6))


def synth_set(unit, photo, sev, n):
    items = []
    for seed in range(30_000, 30_000 + n):
        img, truth = make_sample(seed, unit, photo, sev)
        items.append((img, truth["values"]))
    return items


def real_failures(data):
    cases = failures.load_all(data)
    items = []
    for folder, c in cases:
        img = Image.open(folder / c["image"])
        img.load()
        items.append((img, {k: v for k, v in c["truth"].items() if v is not None}))  # blanked fields are not scored
    return [("saved failures (real, counts only)", items)] if items else []


def score(eng, items):
    """Per item: {letter: (ok, flagged, value)} plus total seconds."""
    out, t0 = [], time.time()
    for img, truth in items:
        try:
            r = eng.run(img)
        except Exception as e:  # an engine that crashes on a page has read nothing from it
            print(f"  {eng.name}: failed on one page ({type(e).__name__}); counted as unread", file=sys.stderr)
            r = dict(values={}, issues={}, low_conf=[])
        ok = compare({k: r["values"].get(k) for k in truth}, truth)
        fl = set(r["issues"]) | set(r["low_conf"])
        out.append({s.letter: (ok[s.key], s.letter in fl, r["values"].get(s.key)) for s in SLOTS if s.key in truth})
    return out, time.time() - t0


def tally(rows, sec, n_img, partner=None):
    f = wf = silent = fa = unread = tot = 0
    for i, row in enumerate(rows):
        for letter, (ok, fl, val) in row.items():
            if partner is not None:  # flag too when the second engine disagrees
                pv = partner[i].get(letter, (None, None, None))[2]
                fl = fl or pv != val
            tot += 1; f += ok; unread += val is None
            wf += (not ok) and fl
            silent += (not ok) and not fl
            fa += ok and fl
    return tot, f, unread, wf, silent, fa, sec / max(n_img, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=20, help="synthetic pages per configuration")
    ap.add_argument("--engines", default=",".join(e.name for e in ocr_engines.ALL))
    ap.add_argument("--failures", action="store_true", help="also score saved real failure cases")
    ap.add_argument("--data", default=os.environ.get("DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
    ap.add_argument("--md", action="store_true", help="print rows for qa/accuracy-trend.md")
    a = ap.parse_args()

    want = a.engines.split(",")
    engines = []
    for e in ocr_engines.ALL:
        if e.name in want or e.name == BASE:
            why = e.unavailable()
            if why:
                print(f"skip {e.name}: {why}")
            else:
                engines.append(e)
    datasets = [(lbl, synth_set(u, p, v, a.n)) for lbl, u, p, v in SYNTH]
    if a.failures:
        datasets += real_failures(a.data)
    hdr = f"{'engine':22} {'fields':>6} {'acc':>6} {'unread':>6} {'wrong&flag':>10} {'SILENT':>6} {'false alarm':>11} {'s/img':>6}"
    for label, items in datasets:
        print(f"\n== {label}  (n={len(items)}) ==\n{hdr}")
        res = {}
        for e in engines:
            res[e.name] = score(e, items)
        for e in engines:
            rows, sec = res[e.name]
            tot, ok, unread, wf, si, fa, per = tally(rows, sec, len(items))
            print(f"{e.name:22} {tot:6} {ok / tot * 100:5.1f}% {unread:6} {wf:10} {si:6} {fa:11} {per:6.1f}")
            if a.md:
                print(f"| {time.strftime('%Y-%m-%d')} | bakeoff {e.name} | {label}, n={len(items)} | {ok / tot * 100:.1f}% | - | {wf} | {si} | - |")
        if BASE in res:
            for e in engines:
                if e.name != BASE:
                    tot, ok, unread, wf, si, fa, _ = tally(res[BASE][0], 0, len(items), partner=res[e.name][0])
                    print(f"{BASE + '+' + e.name:22} {tot:6} {'':>6} {'':>6} {wf:10} {si:6} {fa:11}")


if __name__ == "__main__":
    main()
