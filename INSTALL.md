# Installation

The ultrasound report assistant runs entirely on the local machine. Internet is needed **once**, to
download packages and Tesseract during setup. After that it runs offline and binds to `127.0.0.1` only.

## Requirements
- Python 3.11 or newer
- Tesseract OCR (installed for you by `setup.py` where possible)
- About 500 MB of disk space for the virtual environment

## Windows (the reviewer's machine)
1. Get the project folder onto the machine (zip or copy). No PHI is included.
2. Double-click **`start.bat`**.
   - First run: it installs Python 3.11 via winget if missing, then runs `setup.py`
     (virtual environment, packages, Tesseract via winget, self-check).
   - If Python was just installed, close the window and double-click `start.bat` again.
3. The browser opens at http://127.0.0.1:8000. Later runs skip setup and start immediately.

Windows notes:
- Windows 10/11 with `winget` (App Installer) is assumed. Installing Tesseract shows an administrator prompt.
- Tesseract is not added to PATH by its installer; `setup.py` and `run.py` find it in `C:\Program Files\Tesseract-OCR`.
- Status: reviewed against the Windows code paths but **not yet run on a Windows machine** (see "Windows verification" below).

## macOS
    brew install python@3.11            # if Python 3.11+ is not installed
    python3 setup.py                    # venv + packages + Tesseract (brew) + self-check
    python3 run.py                      # opens http://127.0.0.1:8000
For keystroke typing into Epic, grant **Accessibility** permission to the terminal app
(System Settings > Privacy & Security > Accessibility).

## Linux
    python3 setup.py                    # uses apt-get for Tesseract (asks for sudo)
    .venv/bin/python run.py             # http://127.0.0.1:8000
On other distros, install Tesseract with your package manager first, then run `setup.py`.

## What setup.py does
1. Creates `.venv` and installs `requirements.txt`.
2. Finds Tesseract, or installs it (winget on Windows, brew on macOS, apt on Linux).
3. Self-check: prints the Tesseract version, detected monitors, and OCRs a synthetic page (expect `23 / 23` fields).

It is safe to re-run. If Tesseract is installed somewhere unusual, set `TESSERACT_CMD` to the full path of the executable.

## Running
    python run.py                       # UI at http://127.0.0.1:8000
    python run.py --port 8010 --no-browser

| Setting | Effect |
|---------|--------|
| `USREPORT_DEV=0` | Hides the `/dev` developer UI (use in production) |
| `USREPORT_TYPING=dry` | Rehearses Epic typing without pressing any keys |
| `TESSERACT_CMD` | Path to the Tesseract executable |

Try the Epic typing safely first: open `/epicsim` (dev UI) as a stand-in Epic form, or set `USREPORT_TYPING=dry`.
After clicking **Transcribe to Epic**, click the first Epic field within 5 seconds. Moving the mouse into a
screen corner aborts.

## Docker (development only)
Typing into Epic cannot work from a container, so use this for development and tests.

    docker compose up --build           # http://127.0.0.1:8000
    docker compose run --rm app pytest -q

If `docker` reports permission denied: `sudo usermod -aG docker $USER`, then log out and back in.

## Verify the install
    .venv/bin/python -m pytest -q       # Windows: .venv\Scripts\python -m pytest -q
(Run from the project root; `setup.py` installs pytest.)

## Troubleshooting
| Symptom | Fix |
|---------|-----|
| `Tesseract not found` | Open a new terminal (so PATH refreshes) and re-run, or set `TESSERACT_CMD` |
| `Python 3.11+ required` | Install a newer Python, then re-run `setup.py` |
| Port 8000 in use | `python run.py --port 8010` |
| Keystrokes do nothing on macOS | Grant Accessibility permission to the terminal |
| Browser does not open | Browse to http://127.0.0.1:8000 manually |

## Privacy notes
- `data/` and `images/` are gitignored and may hold PHI. Do not copy them off the machine.
- Logs (`data/logs/usreport.jsonl`) contain slot letters, counts and timings only, never field values.

## Windows verification
On a clean Windows machine, from a Command Prompt in the project folder:

    start.bat
    .venv\Scripts\python -m pytest -q
    .venv\Scripts\python tools\keystroke_helper.py      (dry run; prints the plan)

Expect: the self-check prints `OCR read 23 / 23 fields`, 14 tests pass, and the browser opens with
`build <date>` in the page header. Record the result (Windows version, Python version) in your test log.
