# Project tracker: dev / QA / bizdev in parallel

Updated: 2026-11-01. One row per milestone; each track has its own detail files.

| # | Milestone | Dev | QA | Bizdev | Gate to next |
|---|-----------|-----|----|--------|--------------|
| 0 | Scope + workflow understood | Plan, schema, synthetic data (done) | - | Oct 19 scoping (done); Oct 21 walkthrough (needs transcript); Oct 23 look-alike research plan drafted (L0 desk research not started) | Workflow confirmed with the reviewer |
| 1 | OCR works on real photos | OCR v4 (Oct 25): flagged fields down ~85%, synthetic accuracy 93-99.6%, silent errors 0 (1 at sev 1.0 mm); first real photo 19/23 read, all correct; need more photos | First entries in `qa/test-log.md` | Answer: screenshots possible? advance key? | Wrong-and-silent fields ~0 |
| 2 | Reviewer pilot (real cases, supervised) | Keystroke helper live; polish UI | Clinical checklist per case; log every correction | Agree pilot terms; HIPAA posture documented | the reviewer: net time saved, trusts flags |
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
- (cleared) Docker now works; use `sg docker -c "..."` until you re-login and restart Claude Code.
- Need more real photos (different days/units) to measure real accuracy. Owner: reviewer.
- Oct 21 recording not transcribed. Owner: Chuck.
- Deadline: stable build on the reviewer's Mac before the 3-day job in January; milestone 2 (supervised pilot) not yet started.
- Open bizdev questions: screenshots possible? advance key? pilot terms, HIPAA posture.
