# Plan: ultrasound report transcription assistant

Goal: remove the clerical re-keying of GE ultrasound measurements into an Epic result
template, keeping the human reviewer in the loop. Scope v1: one scan type (MFM anatomy,
billing 76811), phone photos in, keystrokes out, 100% local.

## Decisions (2026-10-22)
- Local/offline only; Docker for dev/test. No real PHI in any cloud tool, ever.
- Input v1: phone photos (screenshots later, pending the reviewer's answer). Handwritten sheet is out of scope.
- Output: keystroke control into Epic; reviewer approves every value first.
- Advance key between Epic fields is unverified (tab vs F2): ask the reviewer. `ADVANCE_KEY` env var.

## Status (2026-10-22, evening)
Docker works. 6/6 tests pass. Extractor (Tesseract + OpenCV adaptive threshold + deskew, two OCR modes
with disagreement flags, repair of common OCR digit errors, cross-checks via Hadlock) reads the first real
photo: 19/23 fields, all correct, 4 unread and flagged. Synthetic benchmark: 85.9-99.6%, silent errors 0-1 per 20 reports.
Not done: keystroke helper live test; UI manual test in a browser; more real photos.

## Next
1. (done) tests + benchmark. Next: drive silent errors to 0 at severity 1.0 (Q-008).
2. (partly done) more real photos; read Cereb GA and GA(AUA) (Q-009, Q-010).
3. Tune preprocessing for glare/skew; consider a local vision model only if Tesseract falls short.
4. Questions for the reviewer: screenshots possible? advance key? other pages needed (M-mode FHR page 3/11,
   anatomy dropdowns)? Does the client allow local software on the VPN Mac?
5. Transcribe the Oct 21 recording into doc/Conversations/.
6. Later: more scan types, per-page capture, packaging as a Mac app, commercial terms.
