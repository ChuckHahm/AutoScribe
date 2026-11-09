#!/usr/bin/env python3
"""Start the server the way a user would and check the pages respond.

    python tools/smoke_test.py            # picks a free port

Checks: `/` and `/dev` return 200, the header shows `build YYYY-MM-DD`, and the UTF-8 header text is not garbled
(a Windows default-encoding bug would show `Â·`). Exits non-zero on failure.
"""
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 0  # set in main() to a free port


def get(path):
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=5) as r:
        return r.status, r.read().decode("utf-8")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    global PORT
    PORT = free_port()
    proc = subprocess.Popen([sys.executable, str(ROOT / "run.py"), "--no-browser", "--port", str(PORT)], cwd=ROOT)
    try:
        for _ in range(40):
            try:
                get("/")
                break
            except OSError:
                if proc.poll() is not None:
                    sys.exit("server exited early")
                time.sleep(0.5)
        else:
            sys.exit("server did not start within 20 s")
        for path in ("/", "/dev"):
            status, body = get(path)
            assert status == 200, f"{path}: HTTP {status}"
            assert re.search(r"build \d{4}-\d{2}-\d{2}", body), f"{path}: no build date in header"
            assert "Â" not in body, f"{path}: garbled UTF-8"
        print("smoke test OK")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
