#!/usr/bin/env python3
"""Types the reviewer-approved values into the focused Epic window.

Runs NATIVELY on the reviewer's machine (a container cannot type into other
apps). Default is a dry run that only prints what it would press.

    python keystroke_helper.py                 # dry run
    python keystroke_helper.py --live          # 5 s countdown, then types
Click the first field (slot A) in Epic during the countdown. Press the mouse into
a screen corner to abort (pyautogui fail-safe). Needs `pip install pyautogui`;
on macOS grant Accessibility permission to the terminal.
"""
import argparse
import json
import time
import urllib.request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000/api/plan")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--countdown", type=int, default=5)
    ap.add_argument("--delay", type=float, default=0.15, help="seconds between keystrokes")
    a = ap.parse_args()

    plan = json.load(urllib.request.urlopen(a.url))
    adv = plan["advance_key"]
    steps = plan["plan"]
    if not a.live:
        for s in steps:
            print(f"{s['slot']}: {'<skip>' if s.get('skip') else s['text']!r} then press {adv}")
        return
    import pyautogui

    pyautogui.FAILSAFE = True
    for i in range(a.countdown, 0, -1):
        print(f"typing in {i}… click slot A in Epic now", flush=True)
        time.sleep(1)
    for s in steps:
        if not s.get("skip"):
            pyautogui.write(s["text"], interval=0.02)
        pyautogui.press(adv)
        time.sleep(a.delay)
    print("done - review the report before signing")


if __name__ == "__main__":
    main()
