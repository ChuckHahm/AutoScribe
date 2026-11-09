# Plan: transcribe approved fields into a running Epic

Status: draft, 2026-11-09. Facts come from this repo; things marked **(assumption)** are not confirmed.

## Goal
After the reviewer approves the 23 extracted values, the app places them into the matching fields of the Epic result
template in a live Epic session. The reviewer then checks Epic and signs. The app never signs, saves or submits.

**Success criteria for the pilot**
- 0 values in the wrong field and 0 wrong values typed, across at least 30 supervised reports.
- A failure or interruption is always visible to the reviewer. A half-filled template is reported as such, never as success.
- Net time saved per report is positive, measured against the current manual re-keying time.

## Where we are
| Piece | State |
|-------|-------|
| `epic.build_plan` / `epic.type_plan` | Types values with pyautogui, one field at a time, pressing an advance key between fields. Countdown, abort event and fail-safe corner exist. |
| Simulator (`/epicsim`) | 23 plain text inputs in tab order. It is a browser page, so it cannot misbehave like Epic. |
| `tools/keystroke_helper.py` | Standalone version that reads `/api/plan`. |
| Safety UI | Dry run mode, Stop button, flagged-field warning before typing. |
| Known risks (tracker) | Q-004 advance key unverified (Tab vs F2). Q-007 typing into the wrong window or field if focus changes. |

The current design is "click the first field, wait 5 s, blind typing". It has **no feedback**: it cannot tell whether Epic
received the characters, whether the cursor is in field A, or whether a popup stole focus. Closing that gap is the heart of this plan.

## Questions that block design (get these answered first)
1. **How is Epic reached?** Native Hyperspace on Windows, a Mac client, Citrix/VDI, or a browser? **(assumption: remote session over VPN from a Mac)** This decides which input methods can work at all.
2. **Advance key:** Tab or F2 (or something else)? Does it behave the same for every field?
3. **Field types:** are all 23 slots plain numeric text boxes, or are some SmartForm elements, dropdowns or fields with auto-format and validation?
4. **Does a practice environment exist?** An Epic training or test patient where wrong entries have no consequence. Without one, every pilot run is on a live chart.
5. **Policy:** does the client allow software that sends keystrokes to Epic? Many organizations restrict automation or macros. This is a go/no-go gate, not a detail, and it must be answered by the client, not assumed.
6. Does the template ever change (new fields, reordered, site-specific builds)?

## Approach options
| Option | Idea | Verdict |
|--------|------|---------|
| A. Keystroke typing (current) | Simulate the keyboard, tab between fields. | Works over any remote session. Blind, so it needs verification added. **Base approach.** |
| B. Clipboard paste per field | Put the value on the clipboard, press paste. | Faster and avoids dropped characters, but clipboard redirection over VDI is often disabled, and it touches the clipboard. Keep as a per-site fallback. |
| C. OS accessibility automation (Windows UI Automation, macOS Accessibility) | Address fields by name, not position. | Most robust when Epic is a native window. Usually **cannot see inside** Citrix or remote windows. Only if the answer to Q1 allows it. |
| D. Screen read-back verification | After typing, capture the Epic window and OCR the values. | We already have OCR and field parsing. Works over any display. **Add to A.** |
| E. Official integration (FHIR, Epic APIs, device interfaces) | Proper data path. | Out of scope: needs IT and procurement, which this project is built to avoid. |

**Recommendation: A, hardened, with D as a closed-loop check, and B as a fallback.** C only if Q1 shows a native window.

## Plan

### Phase 0: Discovery (about 1 week, mostly waiting on people)
- Get answers to the six questions above, in writing, and record them in the decision log.
- Get **sanitized screenshots of the empty Epic template** (we already have labeled examples) and a screen recording of the reviewer filling it manually, with PHI masked. This gives field order, field types and any popups.
- **Gate:** the client permits it (Q5) and a test environment is available (Q4), or the reviewer accepts the supervised-live-chart risk in writing. If not, stop and reconsider.

### Phase 1: Make the simulator realistic, then harden the typer (1-2 weeks)
Build a harder stand-in so problems appear in the lab and not on a chart:
- Fields that are dropdowns or auto-format values, required-field popups, a field that skips focus, slow responses, dropped keystrokes.
- A "remote window" mode: run the simulator inside the Windows VM and drive it over a remote-desktop connection (for example `xfreerdp`), to measure the latency and key-drop behavior that VDI adds.

Harden the typing engine:
- **Start-field check (Q-007):** before typing, confirm the foreground window title matches a configured Epic pattern. Abort if it does not.
- **Focus guard:** re-check the foreground window every N fields. Abort and report "stopped at field X" on any change.
- **Strict key allow-list:** the only keys ever sent are digits, `.`, and the configured advance key. Never Enter, never anything that signs or saves.
- Per-site config file: advance key, per-field delay, tab-skips for non-numeric fields, window title pattern. No code change per site.
- Global abort hotkey (works even if the browser loses focus), plus the existing corner fail-safe.
- Slower typing mode with a per-field delay, chosen from Phase 1 measurements.
- Tests with the fake keyboard (the `kb` parameter already exists) for: abort at each step, focus loss, wrong advance key, empty fields.

### Phase 2: Closed-loop verification (2 weeks)
- After typing, capture the Epic result template and read the 23 fields with the existing OCR pipeline, using a new "Epic template" layout parser.
- Compare to the approved plan and show a diff. **Report mismatches to the reviewer; never auto-correct.**
- Treat "cannot read the template" as "unverified", displayed in the same way as a mismatch.
- Add a template fingerprint (field labels and order). If the fingerprint changes, refuse to type and say why. That catches the case where Epic's template is changed under us.
- **Gate:** on the realistic simulator, every injected fault (wrong field, dropped key, popup) is either prevented or flagged. Silent failures = 0.

### Phase 3: Supervised pilot, test environment first (2-3 weeks)
1. Dry runs while the reviewer watches a screen recording: confirm order and field types against the real template.
2. Typing into the Epic test or training patient, reviewer present, 10 runs.
3. Supervised live use, 30 runs. Log every correction and every verification mismatch (slot letters and counts only, never values).
- **Gate:** 0 misplaced or wrong values, reviewer reports net time saved and trusts the flags.

### Phase 4: Production packaging (2 weeks)
- Windows and macOS permissions walkthrough (macOS Accessibility and Screen Recording), in `INSTALL.md`.
- Per-site config shipped with documentation of each setting.
- Audit log of each transcription: time, slots typed, verification result. No values.
- Failure messages written for a non-technical user: what happened, whether Epic is partly filled, what to do next.
- Regression set from real corrections, as in the tracker's milestone 3.

## Safety principles (fixed, not negotiable)
- The reviewer approves every value before typing. Flagged-and-unedited fields need an explicit confirmation, as they do now.
- The app types a draft only. It never signs, saves, submits or presses Enter.
- Any ambiguity about where the cursor is means stop, not guess.
- Failure must look like failure. "Done" is shown only when typing completed and, from Phase 2 on, verification passed.
- No PHI in logs, tests or the repo. Test screens are synthetic or masked.

## Risks
| Risk | Likelihood / impact | Mitigation |
|------|---------------------|------------|
| Client policy prohibits automation | Unknown / blocks the whole step | Ask in Phase 0 before writing code. |
| Remote session drops or reorders keystrokes | Likely over VDI / wrong values | Latency tests in Phase 1, slower typing, read-back verification, clipboard fallback. |
| Advance key differs by field | Medium / values shift into wrong fields | Per-field advance config, confirmed from the recording. Verification catches the rest. |
| Epic template changes | Medium / silent misplacement | Template fingerprint check refuses to type. |
| Popup or autosave steals focus mid-run | Medium / partial fill | Focus guard, stop and report which field was last typed. |
| No test environment | Medium / pilot on live chart | Treat as a gate. Use the most conservative supervision. |
| Epic read-back OCR is less accurate than for GE pages | Medium / false mismatches | Treat unreadable as "unverified", tune on masked screenshots. |

## Estimated effort
About 8-10 weeks of calendar time if Phase 0 answers arrive quickly. Most of that is waiting on access and supervised runs, not code.
The January deadline in the tracker is tight: a realistic target is Phase 1 and Phase 2 complete, with Phase 3 dry runs, before January.

## Decisions I need from you
1. Who asks the reviewer the six Phase 0 questions, and by when?
2. Is a test or training Epic environment available, or must the pilot be on live charts?
3. Do you want Phase 2 (verification) built before any live pilot? I recommend yes.
