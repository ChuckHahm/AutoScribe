"""Add a misread page by hand to the failure set (data/failures/), e.g. one the tester sent you.

    PYTHONPATH=src python tools/add_failure.py <image> G=147.83 A=45.04 ...

Give the CORRECT value for each slot that was wrong (slot letters A-W, values in Epic units: mm, weeks,
days, grams, percent). Every slot you don't list is assumed to have been read correctly. The image and
values are patient data: they go to the gitignored data/ folder only. Nothing is printed except letters.
"""
import os
import sys
from pathlib import Path

from PIL import Image

from usreport import failures
from usreport.extract import extract
from usreport.schema import SLOT_BY_LETTER

DATA = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[1] / "data"))


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    img = Image.open(argv[1])
    img.load()
    fixes = {}
    for a in argv[2:]:
        letter, _, val = a.partition("=")
        if letter.upper() not in SLOT_BY_LETTER or failures.num(val) is None:
            sys.exit(f"bad argument {a!r}: expected a slot letter A-W, '=' and a number")
        fixes[SLOT_BY_LETTER[letter.upper()].key] = failures.num(val)
    r = extract(img)
    approved = {**r["values"], **fixes}
    folder = failures.save(DATA, img, r, approved, sid=f"manual{len(failures.load_all(DATA)):03d}", source="manual")
    if not folder:
        sys.exit("OCR already reads those slots as given; nothing to record")
    case = failures.load_all(DATA)[-1][1]
    print(f"saved {folder.name}: wrong {','.join(case['wrong'])}; unflagged (silent) {','.join(case['silent']) or 'none'}")


if __name__ == "__main__":
    main(sys.argv)
