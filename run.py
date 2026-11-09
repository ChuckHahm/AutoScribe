#!/usr/bin/env python3
"""Start the review UI natively (no Docker) and open it in the browser.

    python run.py              # UI on http://127.0.0.1:8000
    python run.py --port 8010 --no-browser

Binds to loopback only. Nothing is sent off the machine.
"""
import argparse
import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()

    from usreport import extract
    import shutil

    if not shutil.which(extract.pytesseract.pytesseract.tesseract_cmd) and not Path(extract.pytesseract.pytesseract.tesseract_cmd).exists():
        sys.exit("Tesseract not found. Install it (Windows: https://github.com/UB-Mannheim/tesseract/wiki) "
                 "or set TESSERACT_CMD to tesseract.exe.")

    import uvicorn

    url = f"http://127.0.0.1:{a.port}"
    if not a.no_browser:
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()
    uvicorn.run("usreport.server:app", host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
