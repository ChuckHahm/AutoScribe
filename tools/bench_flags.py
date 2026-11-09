"""How noisy are the review flags on screenshot-like (clean) pages? Counts, over fresh synthetic samples:
  false alarm = correct field that was flagged (validator issue or low OCR confidence)
  SILENT      = wrong field that was NOT flagged (the dangerous ones)
Also lists every wrong field, and writes per-row OCR confidence to a JSON file for choosing LOW_CONF.

    PYTHONPATH=src python tools/bench_flags.py [n_per_unit] [rows.json]
"""
import json
import sys

from usreport.extract import compare, extract
from usreport.schema import MEASUREMENTS, SLOTS
from usreport.synth import make_sample

n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
out = sys.argv[2] if len(sys.argv) > 2 else None
rows, wrong = [], []
print(f"{'unit':5}  {'acc':>6}  {'fields':>6}  {'flagged':>7}  {'false alarm':>11}  {'wrong&flag':>10}  {'SILENT':>6}  {'fully ok':>8}")
for unit in ("mm", "cm"):
    tot = ok_n = flagged = fa = wf = silent = full = 0
    for seed in range(20_000, 20_000 + n):
        img, truth = make_sample(seed, unit, False, 0)
        r = extract(img)
        ok = compare(r["values"], truth["values"])
        full += all(ok.values())
        for s in SLOTS:
            fl = s.letter in r["issues"] or s.letter in r["low_conf"]
            tot += 1; ok_n += ok[s.key]; flagged += fl
            fa += ok[s.key] and fl
            wf += (not ok[s.key]) and fl
            silent += (not ok[s.key]) and not fl
            if not ok[s.key]:
                wrong.append((unit, seed, s.letter, s.key, r["values"][s.key], truth["values"][s.key], fl, r["psm"]))
        for m in MEASUREMENTS:
            rows.append(dict(unit=unit, seed=seed, m=m, conf=r["conf"].get(m),
                             good=all(ok[f"{m}_{x}"] for x in ("mm", "w", "d")),
                             issue=any(s.letter in r["issues"] for s in SLOTS if s.key.startswith(m + "_"))))
    print(f"{unit:5}  {ok_n/tot*100:5.1f}%  {tot:6}  {flagged:7}  {fa:11}  {wf:10}  {silent:6}  {full:>4}/{n}", flush=True)
print("\nWRONG FIELDS (unit seed slot key read true flagged psm):")
for w in wrong:
    print(*w)
if out:
    json.dump(rows, open(out, "w"))
