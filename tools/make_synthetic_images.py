"""Write synthetic GE sonogram images that populate all 23 Epic slots (A-W), with ground truth.

    PYTHONPATH=src python tools/make_synthetic_images.py [outdir]

Each PNG gets a sidecar .json of the expected slot values. Every value is invented.
"""
import json
import sys
from pathlib import Path

from usreport.extract import compare, extract
from usreport.schema import SLOTS
from usreport.synth import make_sample

out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "images" / "synthetic")
out.mkdir(parents=True, exist_ok=True)
CASES = [(101, "mm", False), (102, "mm", False), (103, "mm", False), (104, "cm", False), (105, "mm", True)]
for seed, unit, photo in CASES:
    img, truth = make_sample(seed, unit, photo, 0.5)
    name = f"SYNTHETIC_{seed}_{unit}{'_photo' if photo else ''}"
    img.save(out / f"{name}.png")
    (out / f"{name}.json").write_text(json.dumps(truth["values"], indent=1))
    ok = compare(extract(img)["values"], truth["values"])
    print(f"{name}: {sum(ok.values())}/{len(SLOTS)} slots read back correctly", [s.letter for s in SLOTS if not ok[s.key]] or "")
