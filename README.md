# AutoScribe

A local, offline assistant that reads an ultrasound measurement page and fills in the matching report fields,
so a clinician no longer has to re-key them by hand.

It reads an MFM (maternal-fetal medicine) anatomy-scan measurement page from a screenshot or phone photo,
extracts the 23 report fields (slots A-W), flags anything suspicious, and, only after a **reviewer approves**
every value, types them into the EHR template with a native keystroke helper.

> **Status: prototype.** Not a medical device and not validated for clinical use. The reviewer is responsible
> for checking every value before it is used. Accuracy so far is measured on synthetic pages and a single real photo
> (see [Accuracy](#accuracy)).

## How it works
1. **Capture** a screenshot of the measurement page, or upload a phone photo.
2. **Extract**: Tesseract OCR with label-anchored parsing reads the 23 fields.
3. **Validate**: range, unit, gestational-age, estimated-fetal-weight and repeat-average checks flag doubtful values.
4. **Review**: the reviewer sees every field, with flags, and edits or approves.
5. **Transcribe**: the approved values are typed into the EHR in field order (A-W). The reviewer then checks the result before signing.

## Privacy by design
- **Nothing leaves the machine.** OCR is offline, the UI binds to `127.0.0.1`, and uploaded photos are held in memory only.
- Logs hold slot letters, counts and timings only, never field values or image content.
- `data/` and `images/` are gitignored. Never commit real patient data. Use the built-in synthetic pages for examples and tests.

## Quick start
Needs Python 3.11+ and Tesseract. Internet is required once, for setup.

    python setup.py          # venv, packages, Tesseract, self-check
    python run.py            # http://127.0.0.1:8000

On Windows, double-click `start.bat` (it runs setup on first launch). Full instructions for Windows, macOS, Linux and Docker are in
[INSTALL.md](INSTALL.md).

## Using it
- `/`: capture or upload, review the 23 fields, approve.
- **Transcribe to Epic**: types the approved values. Click the first EHR field within 5 seconds; moving the mouse into a screen corner aborts.
  Set `USREPORT_TYPING=dry` to rehearse without pressing any keys, or use `/epicsim`, a stand-in EHR form, to try it safely.
- `/dev`: developer interface with synthetic pages, upload, benchmark, correction metrics and diagnostics. Hide it with `USREPORT_DEV=0`.
- The software build date is shown in the header of each page.

## Accuracy
Measured with `tools/bench_flags.py` on synthetic GE-style pages (OCR v4, n=20 per set):

| Data set | Field accuracy |
|----------|----------------|
| Clean, mm | 98.0% |
| Clean, cm | 97.4% |
| Phone-photo simulation, mm (mild / moderate / harsh) | 99.6% / 97.8% / 93.5% |

The goal is **zero wrong-and-silent fields**, meaning wrong values that are not flagged. Most remaining errors are flagged for review.
Real-photo accuracy is not established yet: only one real photo has been measured (19 of 23 fields read, all 19 correct, 4 flagged as unread).

## Development
    .venv/bin/python -m pytest -q                 # Windows: .venv\Scripts\python -m pytest -q
    python tools/bench_flags.py                   # synthetic accuracy and flag counts
    python tools/bench_severity.py                # accuracy by photo severity
    docker compose up --build                     # dev in Docker (cannot type into the EHR from a container)

| Path | Purpose |
|------|---------|
| `src/usreport/schema.py` | Report slots A-W |
| `src/usreport/extract.py` | Tesseract OCR and label-anchored parsing |
| `src/usreport/validate.py` | Range, unit, GA, EFW and repeat-average checks |
| `src/usreport/hadlock.py` | Formulas used to generate synthetic data and cross-check OCR |
| `src/usreport/synth.py` | Synthetic GE-style pages and phone-photo degradation |
| `src/usreport/server.py` | FastAPI review UI and `/api/plan` |
| `tools/keystroke_helper.py` | Native typing helper (dry run by default) |
| `tests/` | Pipeline, transcription and logging tests |

Project status and milestones: [TRACKER.md](TRACKER.md). Design notes: [doc/PLAN.md](doc/PLAN.md).

## License
No license has been chosen yet, so all rights are reserved by default. Add a `LICENSE` file before inviting reuse or contributions.
