"""Progress and error log history, one JSON object per line, rotated on disk.

PHI rule: log slot letters, counts, sizes and timings only. Never a field value or image content.
"""
import json
import logging
import logging.handlers
import time
from pathlib import Path

log = logging.getLogger("usreport")
_FILE: Path | None = None
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


class _Json(logging.Formatter):
    def format(self, r):
        d = dict(t=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r.created)), level=r.levelname,
                 src=r.name.removeprefix("usreport.") if r.name != "usreport" else "app", msg=r.getMessage())
        if r.exc_info:
            d["exc"] = self.formatException(r.exc_info)
        return json.dumps(d)


def setup(data_dir: Path):
    """Attach the rotating file handler (idempotent). Falls back to stderr only if the folder is unwritable."""
    global _FILE
    log.setLevel(logging.DEBUG)
    if _FILE:
        return _FILE
    try:
        d = Path(data_dir) / "logs"
        d.mkdir(parents=True, exist_ok=True)
        _FILE = d / "usreport.jsonl"
        h = logging.handlers.RotatingFileHandler(_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        h.setFormatter(_Json())
        log.addHandler(h)
    except OSError as e:
        _FILE = None
        log.addHandler(logging.StreamHandler())
        log.error("log file unavailable, logging to stderr only: %s", e)
    return _FILE


def tail(n=200, min_level="DEBUG"):
    """Newest-first log records, reading rotated files as needed."""
    if not _FILE:
        return []
    floor = LEVELS.index(min_level) if min_level in LEVELS else 0
    out = []
    for f in [_FILE, *[_FILE.with_name(f"{_FILE.name}.{i}") for i in range(1, 6)]]:
        if not f.exists():
            continue
        for line in reversed(f.read_text(encoding="utf-8").splitlines()):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if LEVELS.index(r["level"]) >= floor:
                out.append(r)
                if len(out) >= n:
                    return out
    return out
