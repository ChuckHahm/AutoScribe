"""Place approved values into the Epic result template by typing them, field by field.

Runs on the reviewer's own machine (the service is local), so it drives the keyboard directly.
The reviewer clicks the first Epic field (slot A) during the countdown, then reviews the filled
report in Epic before signing. Mouse into a screen corner aborts (pyautogui fail-safe).
"""
import threading
import time

from .logs import log
from .schema import SLOTS

log = log.getChild("epic")


def build_plan(values):
    """[{slot, text}|{slot, skip}] in Epic tab order A-W. Empty values are skipped (left blank in Epic)."""
    plan = []
    for s in SLOTS:
        v = values.get(s.key)
        plan.append(dict(slot=s.letter, text="", skip=True) if v in (None, "") else dict(slot=s.letter, text=f"{float(v):g}"))
    return plan


def type_plan(plan, advance_key, progress, abort: threading.Event, countdown=5, delay=0.15, dry_run=False, kb=None):
    """Type the plan. progress(step, total, message) is called as it goes. Returns the number of fields typed.

    kb: object with write(text, interval) and press(key); defaults to pyautogui. Raises RuntimeError if aborted.
    """
    if kb is None and not dry_run:
        try:
            import pyautogui
        except Exception as e:  # not installed, or no display
            raise RuntimeError(f"keyboard control unavailable ({type(e).__name__}); run setup.py") from e
        pyautogui.FAILSAFE = True
        kb = pyautogui
    total = len(plan)
    for i in range(countdown, 0, -1):
        if abort.is_set():
            raise RuntimeError("aborted during countdown")
        progress(0, total, f"Click the first Epic field (A) now. Typing starts in {i} s")
        time.sleep(1 if not dry_run else 0)
    typed = 0
    for n, s in enumerate(plan, 1):
        if abort.is_set():
            raise RuntimeError(f"aborted before field {s['slot']}")
        if not s.get("skip"):
            if not dry_run:
                kb.write(s["text"], interval=0.02)
            typed += 1
        if not dry_run:
            kb.press(advance_key)
        log.debug("field %s %s", s["slot"], "skipped" if s.get("skip") else "typed")
        progress(n, total, f"Field {s['slot']} {'left blank' if s.get('skip') else 'typed'} ({n}/{total})")
        time.sleep(delay if not dry_run else 0)
    return typed
