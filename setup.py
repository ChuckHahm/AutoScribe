#!/usr/bin/env python3
"""Create the whole runtime environment. Safe to re-run. Needs only Python 3.11+ (stdlib).

    python setup.py            # venv + packages + Tesseract + self-check

The one step that needs internet is downloading packages / Tesseract. Runtime is offline.
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WIN = platform.system() == "Windows"


def run(cmd, **kw):
    print("  $", " ".join(map(str, cmd)))
    return subprocess.run(cmd, **kw)


def tesseract_path():
    """Same lookup as usreport.extract._find_tesseract (duplicated: the app can't import before the venv exists)."""
    win = (r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe")
    for c in (os.environ.get("TESSERACT_CMD"), shutil.which("tesseract"), *win):
        if c and os.path.exists(c):
            return c


def install_tesseract():
    if WIN and shutil.which("winget"):
        run(["winget", "install", "-e", "--id", "UB-Mannheim.TesseractOCR", "--silent",
             "--accept-package-agreements", "--accept-source-agreements"])
    elif platform.system() == "Darwin" and shutil.which("brew"):
        run(["brew", "install", "tesseract"])
    elif shutil.which("apt-get"):
        run(["sudo", "apt-get", "install", "-y", "tesseract-ocr"])
    else:
        sys.exit("Install Tesseract manually (Windows: https://github.com/UB-Mannheim/tesseract/wiki), then re-run.")


def main():
    sys.stdout.reconfigure(line_buffering=True)  # keep our lines in order with child-process output
    ap = argparse.ArgumentParser()
    ap.add_argument("--venv", default=str(ROOT / ".venv"))
    a = ap.parse_args()
    if sys.version_info < (3, 11):
        sys.exit(f"Python 3.11+ required, found {sys.version.split()[0]}")

    venv = Path(a.venv)
    py = venv / ("Scripts/python.exe" if WIN else "bin/python")
    print("1/3 Python environment")
    if not py.exists():
        run([sys.executable, "-m", "venv", str(venv)], check=True)
    run([str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", str(ROOT / "requirements.txt")], check=True)

    print("2/3 Tesseract OCR")
    if not tesseract_path():
        install_tesseract()
    t = tesseract_path()
    if not t:
        sys.exit("Tesseract still not found after install. Open a new terminal and re-run, or set TESSERACT_CMD.")
    print("  found", t)

    print("3/3 Self-check")
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    code = ("from usreport import extract, capture, synth; import pytesseract;"
            "print('  tesseract', pytesseract.get_tesseract_version());"
            "print('  monitors', capture.monitors());"
            "img, t = synth.make_sample(1, 'mm', False, 0); r = extract.extract(img);"
            "print('  OCR read', sum(v is not None for v in r['values'].values()), '/ 23 fields from a synthetic page')")
    run([str(py), "-c", code], check=True, env=env)
    print("\nReady. Start with:", "start.bat" if WIN else "python run.py")


if __name__ == "__main__":
    main()
