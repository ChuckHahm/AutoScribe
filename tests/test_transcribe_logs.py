import os
import tempfile
import threading
import time

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())

import pytest
from fastapi.testclient import TestClient

from usreport import epic, logs, server
from usreport.schema import SLOTS


class FakeKb:
    def __init__(self):
        self.events = []

    def write(self, text, interval=0):
        self.events.append(("w", text))

    def press(self, key):
        self.events.append(("p", key))


def test_build_plan_skips_blanks_and_formats_numbers():
    plan = epic.build_plan({"bpd_mm": 49.0, "bpd_w": 20, "hc_mm": None, "ac_mm": ""})
    assert [p["slot"] for p in plan] == [s.letter for s in SLOTS]
    assert plan[0] == dict(slot="A", text="49") and plan[1]["text"] == "20"
    assert plan[3].get("skip") and plan[6].get("skip")


def test_type_plan_types_in_tab_order_and_presses_advance_for_every_slot():
    plan = epic.build_plan({"bpd_mm": 49.0, "bpd_w": 20})
    kb, steps = FakeKb(), []
    n = epic.type_plan(plan, "tab", lambda *a: steps.append(a), threading.Event(), countdown=0, delay=0, kb=kb)
    assert n == 2
    assert kb.events[:4] == [("w", "49"), ("p", "tab"), ("w", "20"), ("p", "tab")]
    assert sum(e == ("p", "tab") for e in kb.events) == len(SLOTS)  # blanks still advance, so later fields line up
    assert steps[-1][0] == len(SLOTS)


def test_type_plan_abort_stops_midway():
    plan = epic.build_plan({"bpd_mm": 1, "bpd_w": 2, "bpd_d": 3})
    ab, kb = threading.Event(), FakeKb()

    def prog(step, total, msg):
        if step == 1:
            ab.set()

    with pytest.raises(RuntimeError, match="aborted"):
        epic.type_plan(plan, "tab", prog, ab, countdown=0, delay=0, kb=kb)
    assert ("w", "2") not in kb.events


def test_logs_roundtrip_and_level_filter():
    logs.log.getChild("test").info("hello progress")
    logs.log.getChild("test").error("boom")
    allr = logs.tail(10)
    assert allr[0]["msg"] == "boom" and allr[0]["level"] == "ERROR"  # newest first
    assert [r["msg"] for r in logs.tail(10, "ERROR")][0] == "boom"
    assert all(r["level"] == "ERROR" for r in logs.tail(50, "ERROR"))


def test_api_transcribe_dry_run_logs_progress_without_values(monkeypatch):
    monkeypatch.setattr(server, "TYPING_MODE", "dry")
    c = TestClient(server.app)
    r = c.post("/api/transcribe", json=dict(values={"bpd_mm": 49.123, "bpd_w": 20}, original={"bpd_mm": 48}, flagged=["A"], countdown=0))
    assert r.status_code == 200 and r.json()["corrected"][0] == "A"
    for _ in range(50):
        j = c.get("/api/transcribe/status").json()
        if j["status"] != "running":
            break
        time.sleep(0.1)
    assert j["status"] == "done" and j["typed"] == 2 and "DRY RUN" in j["message"]
    text = " ".join(x["msg"] for x in c.get("/api/logs?n=100").json()["logs"])
    assert "transcribe requested" in text and "transcribe finished" in text
    assert "49.123" not in text  # PHI rule: no values in logs
    assert c.post("/api/transcribe", json=dict(values={})).status_code == 400


def test_client_errors_land_in_history_and_pages_render():
    c = TestClient(server.app)
    c.post("/api/log", json=dict(level="error", msg="js exploded"))
    top = c.get("/api/logs?n=5&level=ERROR").json()["logs"][0]
    assert top["src"] == "browser" and top["msg"] == "js exploded"
    for path in ("/", "/dev", "/epicsim", "/sim"):
        assert c.get(path).status_code == 200
    assert '"letter": "A"' in c.get("/epicsim").text
