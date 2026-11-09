# Ultrasound report assistant (local, offline)

Reads an MFM anatomy-scan measurement page (screenshot or phone photo), extracts the
23 Epic fields (A-W), flags anything suspicious, and after the reviewer approves,
types the values into Epic with a native keystroke helper.

**Nothing leaves the machine.** OCR is Tesseract (offline). The UI binds to 127.0.0.1.
Uploaded photos are held in memory only. `data/` and `images/` are gitignored (PHI).

## Run natively (no Docker; how it runs on the reviewer's machine)
    python setup.py                    # once: venv, packages, Tesseract, self-check (Windows: start.bat does this on first run)
    python run.py                      # http://127.0.0.1:8000 (Windows: start.bat)
setup.py installs Tesseract via winget (Windows), brew (macOS) or apt (Linux). Override the location with `TESSERACT_CMD`.
- `/`     user interface: capture the screen, review the 23 fields, approve.
- `/dev`  developer interface: synthetic pages, upload, benchmark, latest plan + correction metrics, system diagnostics.
  Hide it in production with `USREPORT_DEV=0`.
- **Transcribe to Epic** (Report page): types the reviewed values into the Epic template, fields A-W in tab order. After clicking,
  click the first Epic field within 5 s. Mouse into a screen corner, or Stop, aborts. Set `USREPORT_TYPING=dry` to rehearse without
  pressing any keys; `/epicsim` (dev UI) is a stand-in Epic form for trying it safely.
- **Logs:** progress and errors go to `data/logs/usreport.jsonl` (rotating, 5 x 1 MB) and show in Developer > Logs.
  Logs hold slot letters, counts and timings only, never field values or image content.

## Run (dev, Docker)
    docker compose up --build          # http://127.0.0.1:8000
    docker compose run --rm app pytest -q

If `docker` says permission denied: add yourself to the group (`sudo usermod -aG docker $USER`,
then log out/in) or start Docker Desktop and `docker context use desktop-linux`.

Benchmark (synthetic photos at rising difficulty) and real-photo check:

    docker compose run --rm app python tools/bench_severity.py
    docker compose run --rm -v "$PWD/images:/real:ro" app python tools/run_on_photo.py "/real/IMG_5701 START.png"

## Layout
- `src/usreport/schema.py`   Epic slots A-W
- `src/usreport/hadlock.py`  formulas (generate synthetic data, cross-check OCR)
- `src/usreport/synth.py`    synthetic GE-style pages + phone-photo degradation
- `src/usreport/extract.py`  Tesseract OCR -> label-anchored parsing
- `src/usreport/validate.py` range / unit / GA / EFW / repeat-average checks
- `src/usreport/server.py`   FastAPI review UI + `/api/plan`
- `tools/keystroke_helper.py` run natively on the reviewer's machine (dry run by default)
