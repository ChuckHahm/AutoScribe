# CLAUDE.md

Guidance for Claude Code in this project.

## What this is
A local, offline ultrasound report assistant. It OCRs a GE MFM anatomy-scan measurement page (phone photo or screenshot), extracts the 23 Epic fields (slots A-W), flags suspicious values, and after the reviewer approves, types the values into Epic with a keystroke helper. Scope v1 is one scan type (MFM anatomy). Current status: `TRACKER.md`.

## Hard rules
- **No PHI in the repo, logs, or any cloud tool.** Use synthetic data (`images/synthetic/`, `usreport.synth`) for examples and tests. `data/` and `images/` are gitignored and may hold PHI. Never print, summarize or upload real image contents or field values from them without being asked.
- **Everything stays local.** OCR is Tesseract (offline). The UI binds to `127.0.0.1` only. Don't add network calls, telemetry or cloud OCR.
- **The reviewer approves every value** before anything is typed. Don't add auto-submit paths.
- **Wrong-and-silent is the metric that matters:** a wrong field that isn't flagged. Prefer flagging over guessing. Any OCR or validation change must keep silent errors at ~0.
- Logs hold slot letters, counts and timings only, never field values.
- Don't press real keystrokes while testing. Use `USREPORT_TYPING=dry` or the `/epicsim` page.

## Commands
    python setup.py                         # one-time: venv, packages, Tesseract, self-check
    python run.py                           # UI at http://127.0.0.1:8000 (--port N, --no-browser)
    .venv/bin/python -m pytest -q           # tests (Windows: .venv\Scripts\python); run from the project root
    python tools/bench_flags.py             # synthetic accuracy and flag counts; log results in qa/accuracy-trend.md
    python tools/bench_severity.py          # accuracy by photo severity
    python tools/run_on_photo.py <path>     # one real photo; output may reflect PHI, don't paste it
    docker compose up --build               # dev in Docker (can't type into Epic from a container)

Install details are in `INSTALL.md`.

Env vars: `USREPORT_DEV=0` hides `/dev`, `USREPORT_TYPING=dry`, `ADVANCE_KEY` (default `tab`; unverified, may be F2), `TESSERACT_CMD`, `DATA_DIR`, `USREPORT_BIND`.

## Code map (`src/usreport/`)
- `schema.py`: Epic slots A-W
- `extract.py`: Tesseract OCR, then label-anchored parsing (current build: OCR v4)
- `validate.py`: range, unit, GA, EFW and repeat-average checks that produce flags
- `hadlock.py`: formulas used to generate synthetic data and cross-check OCR
- `synth.py`: synthetic GE-style pages and phone-photo degradation
- `capture.py`: screen capture. `epic.py`: Epic typing plan. `logs.py`: rotating JSONL logs
- `server.py`: FastAPI app with the review UI (`/`), dev UI (`/dev`), `/epicsim` and `/api/plan`
- `tools/keystroke_helper.py`: native typing helper (dry run by default)
- `tests/`: `test_pipeline.py`, `test_transcribe_logs.py`

## Three parallel tracks
- **Dev**: `doc/PLAN.md`, `src/`, `tests/`
- **QA**: `qa/` (private, not in the public repo; test log, issues, accuracy trend, clinical checklist, open questions)
- **Bizdev**: `bizdev/` (private, not in the public repo; stakeholders, hypotheses H1-H6, terms, compliance, decision log, meetings, look-alike research plan)

`TRACKER.md` is the milestone table. Update it, and `qa/accuracy-trend.md` after any benchmark run, when something ships. Append decisions to `bizdev/decision-log.md` (append-only).

## Conventions
- Label facts by source and guesses as guesses in bizdev docs.
- Keep QA numbers reproducible: record the build (e.g. OCR v4), dataset, severity and n.
- The look-alike research workflow has a project skill: `.claude/skills/lookalike-research`.
