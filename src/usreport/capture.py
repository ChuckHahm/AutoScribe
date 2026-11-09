"""Grab the screen on the local machine (the operational input; photos are a dev-only fallback).

mss is pure Python and works on Windows, macOS and X11. The image goes straight to
the extractor in memory; nothing is written to disk.
"""
import time

import mss
from PIL import Image


def monitors():
    """[(index, width, height)] for each physical monitor (1-based, as mss numbers them)."""
    with mss.mss() as sct:
        return [(i, m["width"], m["height"]) for i, m in enumerate(sct.monitors) if i > 0]


def grab(monitor=1, delay=0.0, region=None):
    """Screenshot of one monitor (or a region (left, top, width, height) of it) as an RGB image.

    delay: seconds to wait first, so the reviewer can bring the GE page to the front.
    """
    if delay:
        time.sleep(delay)
    with mss.mss() as sct:
        if not 1 <= monitor < len(sct.monitors):
            raise ValueError(f"monitor {monitor} not found; have 1..{len(sct.monitors) - 1}")
        box = dict(sct.monitors[monitor])
        if region:
            l, t, w, h = region
            box = dict(left=box["left"] + l, top=box["top"] + t, width=w, height=h)
        shot = sct.grab(box)
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
