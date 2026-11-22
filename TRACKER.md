# Project tracker: dev / QA / bizdev in parallel

Updated: 2026-11-18 (end of day). One row per milestone; each track has its own detail files.

| # | Milestone | Dev | QA | Bizdev | Gate to next |
|---|-----------|-----|----|--------|--------------|
| 0 | Scope + workflow understood | Plan, schema, synthetic data (done) | - | Oct 19 scoping (done); Oct 21 walkthrough (needs transcript); Oct 23 look-alike research plan drafted (L0 desk research not started) | Workflow confirmed with the reviewer |
| 1 | OCR works on real screen captures | OCR v4 (Oct 25): flagged fields down ~85%, synthetic accuracy 93-99.6%, silent errors 0 (1 at sev 1.0 mm); first real photo 19/23 read, all correct; need more photos. Nov 17-18: RapidOCR added as a second-engine cross-check (`crosscheck.py`, shipped in f346a3b); any field where Tesseract and RapidOCR disagree is flagged, values unchanged. Synthetic, embedded font, OpenCV 4.10: shipped pipeline silent 0 / 0 (clean mm / cm, n=100; Tesseract alone 1 / 1); bake-off photo mm sev 0.6 silent 3 (Tesseract) -> 0 (with cross-check); rapidocr alone 100 / 100 / 97.4%. Percentile decimal-loss fixed and flagged (`_pct`). Runtime input is screen captures, not photos. ~6-7 s per page. Failure capture (`USREPORT_CAPTURE_FAILURES=1`) added. Nov 18: simulated screen now shows at 1:1 (it was shrunk to fit the window, which cost Tesseract its resolution), flag wording fixed, `main` at b16f924 with CI green on Linux, macOS and Windows | First entries in `qa/test-log.md` | Screen captures confirmed as runtime input (Nov 17). Open: advance key? | Wrong-and-silent fields ~0 |
| 2 | Reviewer pilot (real cases, supervised) | Keystroke helper live; polish UI. Chuck is doing a manual install-and-test from a fresh clone (`testenv/`, gitignored) before approving a build for the user test | Clinical checklist per case; log every correction | Agree pilot terms; HIPAA posture documented | the reviewer: net time saved, trusts flags |
| 3 | Daily use before January (the reviewer's 3-day job starts) | Stabilize, packaging for the reviewer's Mac | Regression set from real corrections | Commercial terms decided | Stable for 2+ weeks |
| 4 | Productize (if warranted) | More scan types, installer | Per-scan-type accuracy | Market validation, client license, equity terms | Go/no-go on product |

## Files
- Dev: `doc/PLAN.md`, `README.md`, `src/`, `tests/`
- QA: `qa/` (kept private: test log, issues, accuracy trend, clinical checklist)
- Bizdev: `bizdev/` (kept private)

## Weekly rhythm
1. Update the milestone table above.
2. Dev: note what shipped. QA: add runs/issues. Bizdev: add meeting notes, update hypotheses and decision log.
3. Anything blocking another track goes in "Blockers" below.

## Blockers
- Page size on screen drives Tesseract accuracy (synthetic, 1920x1080 canvas): 20/23 fields correct with the page at full size, 3/23 at 70%, 1/23 at 55%; RapidOCR holds up better (23/23 at 70%, 21/23 at 55%) but also fails when the page is small. Enlarging in software afterwards does not recover it. Likely part of the reviewer's 80-85%. Tell the reviewer to show the GE page as large as possible (full screen); confirm against real captures. Owner: Chuck / Brian.
- Nov 16 call, not yet acted on: (1) compute the GA fields with Hadlock instead of OCR (`hadlock.py` is used only for cross-checks today; the "lowest of several formulas" detail is not implemented; Brian called it the easiest win); (2) form-completion approach undecided (handwritten checklist, default-to-normal, blank-first UI); (3) the reviewer thinks 23 fields alone will not interest another clinic, wants the whole form; (4) another machine brand's output format failed; (5) other report types (growth, dating); (6) compensation. Decisions are not yet in `bizdev/decision-log.md`.
- Nov 21 call (`bizdev/meetings/2026-11-21-product-discovery.md`, decisions logged): $5,000 (1099) agreed for work to date, not yet paid; report completion (~$40K reviewer estimate) NOT committed, viability test first on de-identified handwritten sheets (owner: Brian to send, Chuck to assess); Chuck to run market discovery through his contacts; Brian to confirm the reviewer's January date. H7 and H8 added.
- Known limits: RapidOCR 1.4.4 does not install on Python 3.13+ (app falls back to Tesseract alone and the review screen says the cross-check did not run; untested). Header shows "build 2026-11-09": not yet checked whether that is stale.
- Note (2026-11-17): the runtime version reads screen captures of the on-screen character strings, not phone photos. Photo-severity benchmarks are a stress test only; weight accuracy work toward clean screen captures (scaling/resolution, e.g. maximized window helps per the Nov 16 call).
- (decided 2026-11-17/18) RapidOCR runs as the cross-check beside Tesseract. Open: re-run `tools/bench_flags.py` and `tools/bakeoff.py --failures` on real screen captures (synthetic pages use a stand-in font, not the GE font); check whether Tesseract-alone is still needed. Owner: Chuck.
- (cleared) Docker now works; use `sg docker -c "..."` until you re-login and restart Claude Code.
- Need more real screen captures of failed reads (different days/units); the runtime input is screen captures, not photos. Owner: Brian (collecting this week).
- Oct 21 recording not transcribed. Owner: Chuck.
- Deadline: stable build on the reviewer's Mac before the 3-day job in January; milestone 2 (supervised pilot) not yet started.
- Open bizdev questions: exact January start date; EIN or SSN for the 1099; screenshots possible? advance key? pilot terms, HIPAA posture.
