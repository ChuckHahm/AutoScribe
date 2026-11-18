# Installation

The ultrasound report assistant runs entirely on the local machine. Internet is needed **once**, to
download packages and Tesseract during setup. After that it runs offline and binds to `127.0.0.1` only.

## Requirements
- Python 3.11 or 3.12. The second OCR engine used for the cross-check (RapidOCR) does not install on Python 3.13+ yet; on 3.13+ the app runs on Tesseract alone and the review screen says the cross-check did not run.
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
- Status: tested on a clean Windows 10 Enterprise VM (no winget, no Python) on 2026-11-09. `start.bat` installs Python 3.11 from python.org and Tesseract 5.4 and starts the server. See "Known issue: OCR differs by Tesseract version" below.

## macOS
Status: **not yet tested on a Mac.** The steps below follow what `setup.py` does on Linux, so expect to adjust. Please record what
you hit (macOS version, chip, Python and Tesseract versions) in `qa/test-log.md`. Homebrew installs Tesseract 5.x, so read
"Known issue: OCR differs by Tesseract version" below before trusting results.

1. Install Homebrew (https://brew.sh) if you don't have it, then Python 3.11:

        brew install python@3.11

2. Run setup with that Python explicitly. The `python3` on a Mac is often 3.9 (Apple's) or a newer Homebrew version, and `setup.py` stops with
   "Python 3.11+ required" if it is older than 3.11:

        python3.11 setup.py                 # venv + packages + Tesseract (brew install tesseract) + self-check

3. Start the app **with the venv's Python**. Plain `python3 run.py` uses the system Python, which does not have the packages:

        .venv/bin/python run.py             # opens http://127.0.0.1:8000

4. Grant permissions (System Settings > Privacy & Security), to the app you launch from (Terminal, iTerm, VS Code), then quit and reopen it:
   - **Accessibility**: needed to type into Epic. Without it, keystrokes silently do nothing.
   - **Screen Recording**: needed for the **Capture screen** button. Without it, the capture is blank or shows only the desktop wallpaper.

If `tesseract` is not found after setup (Apple Silicon installs to `/opt/homebrew/bin`, Intel to `/usr/local/bin`), open a new terminal so
the Homebrew PATH loads, or set `TESSERACT_CMD=/opt/homebrew/bin/tesseract`.

## Linux
Status: tested on Ubuntu 20.04 (X11, Tesseract 4.1.1, Python 3.11 via pyenv). This is the reference platform the OCR was tuned on.

1. Install Python 3.11 or newer **with the venv module**. Ubuntu 20.04's default Python is 3.8, which is too old; use pyenv or the
   deadsnakes PPA. On Debian/Ubuntu, if `python -m venv` complains about `ensurepip`, install the matching `python3.X-venv` package.
2. Run setup with that Python:

        python3.11 setup.py                 # apt-get install tesseract-ocr (asks for sudo), venv, packages, self-check
        .venv/bin/python run.py             # http://127.0.0.1:8000

3. Other distros (no `apt-get`): install Tesseract with your package manager first (for example `dnf install tesseract` or
   `pacman -S tesseract`), then run `setup.py`. It will find the existing install.

Typing into Epic and screen capture need a graphical **X11** session. Under Wayland, synthetic keystrokes (pyautogui) generally do not
reach other windows; choose "Ubuntu on Xorg" (or the X11 session of your desktop) at the login screen. Over SSH or in Docker there is
no display, so use uploads and `USREPORT_TYPING=dry`.
Distros newer than Ubuntu 20.04 may ship Tesseract 5.x; see "Known issue: OCR differs by Tesseract version" below.

## What setup.py does
1. Creates `.venv` and installs `requirements.txt`.
2. Finds Tesseract, or installs it (winget on Windows, brew on macOS, apt on Linux).
3. Self-check: prints the Tesseract version, detected monitors, and OCRs a synthetic page (23 / 23 fields with Tesseract 4.1, 19 / 23 with Tesseract 5.4; see Known issue below).

It is safe to re-run. If Tesseract is installed somewhere unusual, set `TESSERACT_CMD` to the full path of the executable.

## Running
    python run.py                       # UI at http://127.0.0.1:8000
    python run.py --port 8010 --no-browser

| Setting | Effect |
|---------|--------|
| `USREPORT_DEV=0` | Hides the `/dev` developer UI (use in production) |
| `USREPORT_TYPING=dry` | Rehearses Epic typing without pressing any keys |
| `TESSERACT_CMD` | Path to the Tesseract executable |
| `USREPORT_CAPTURE_FAILURES=1` | Saves pages the reviewer corrects to `data/failures/` (see below). Off by default |

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
| Keystrokes do nothing on macOS | Grant Accessibility permission to the app you launch from (Terminal, iTerm, VS Code), then restart it |
| Capture screen is blank on macOS | Grant Screen Recording permission to the same app, then restart it |
| `ModuleNotFoundError` (fastapi, uvicorn...) on macOS/Linux | You ran `python3 run.py`; use `.venv/bin/python run.py` |
| Keystrokes do nothing on Linux | You are on Wayland; log in to an X11 session |
| Browser does not open | Browse to http://127.0.0.1:8000 manually |

## Optional: collect misreads and compare OCR engines (development)
To analyse where OCR goes wrong, start the app with `USREPORT_CAPTURE_FAILURES=1` (for example `USREPORT_CAPTURE_FAILURES=1 .venv/bin/python run.py`).
Any page where the reviewer changes a value is saved, image and values, to `data/failures/`. **This is patient data on disk**, so only
enable it where that is allowed, and delete the folder when finished (`rm -r data/failures`). Then, from the project root:

    PYTHONPATH=src .venv/bin/python tools/failure_report.py            # misreads by kind and slot; counts only
    PYTHONPATH=src .venv/bin/python tools/bakeoff.py -n 20 --failures  # compare OCR engines

On Windows use `set PYTHONPATH=src` and `.venv\Scripts\python`. Other engines are not part of the normal install. To try RapidOCR, install it in a
**separate** virtual environment (it pulls in its own OpenCV and a newer NumPy that would clash with the project's pinned versions) and borrow
the project's packages:

    python3.11 -m venv ~/ocr-venv && ~/ocr-venv/bin/pip install rapidocr-onnxruntime
    PYTHONPATH=src:.venv/lib/python3.11/site-packages ~/ocr-venv/bin/python tools/bakeoff.py -n 20 --engines tess_current,rapidocr

(Tested on Linux. On macOS, `ocrmac` adds Apple's Vision engine as `apple_vision`; that adapter is untested.)

## Privacy notes
- `data/` and `images/` are gitignored and may hold PHI (including `data/failures/` if you enable capture). Do not copy them off the machine.
- Logs (`data/logs/usreport.jsonl`) contain slot letters, counts and timings only, never field values.

## Windows verification
On a clean Windows machine, from a Command Prompt in the project folder:

    start.bat
    .venv\Scripts\python -m pytest -q
    .venv\Scripts\python tools\keystroke_helper.py      (dry run; prints the plan)

Expect: the self-check prints `OCR read N / 23 fields`, at least 13 of 14 tests pass (see Known issue), and the browser opens with
`build <date>` in the page header. Record the result (Windows version, Python version) in your test log.

## Known issue: OCR differs by Tesseract version
The extractor was tuned on Tesseract 4.1.1 (Linux/Docker). Homebrew (macOS) and newer Linux distros install Tesseract 5.x, which is expected to behave like Windows below but has **not** been measured. With Tesseract 5.4 on Windows, the same clean synthetic page reads
19 / 23 fields and `test_clean_mm_and_cm_roundtrip` fails (different GA and percentile fields each run). Flags still work, but
real-photo accuracy on Windows has **not** been measured. Until the extractor is re-tuned for Tesseract 5, treat Windows
results as unverified and compare against `qa` accuracy numbers from a Tesseract 4.1 run.
