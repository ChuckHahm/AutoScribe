import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from fastapi.testclient import TestClient

from usreport import failures, server
from usreport.extract import extract
from usreport.synth import make_sample


def test_save_only_when_reviewer_changed_something(tmp_path):
    img, truth = make_sample(5, "mm", False, 0)
    r = extract(img)
    approved = dict(r["values"])
    assert failures.save(tmp_path, img, r, approved) is None  # approved as read: not a failure
    approved["hc_mm"] = (approved["hc_mm"] or 100) + 5  # reviewer fixed HC
    folder = failures.save(tmp_path, img, r, approved, sid="t1")
    assert folder and (folder / "image.png").exists()
    (_, case), = failures.load_all(tmp_path)
    assert case["wrong"] == ["D"] and case["truth"]["hc_mm"] == approved["hc_mm"]
    assert set(case["silent"]) <= set(case["wrong"])


def test_blanked_field_counts_as_invented_value(tmp_path):
    img, _ = make_sample(6, "mm", False, 0)
    r = extract(img)
    folder = failures.save(tmp_path, img, r, dict(r["values"], bpd_mm=None))  # reviewer cleared BPD
    (_, case), = failures.load_all(tmp_path)
    assert folder and case["wrong"] == ["A"]
    assert failures.save(tmp_path, img, r, dict(r["values"])) is None  # all as read (unread stays unread): no case


def test_server_capture_is_off_by_default_and_on_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA", tmp_path)
    c = TestClient(server.app)

    def run():
        r = c.post("/api/synthetic?unit=mm&seed=7").json()
        vals = dict(r["values"], fl_mm=(r["values"]["fl_mm"] or 30) + 3)
        c.post("/api/approve", json=dict(values=vals, original=r["values"], id=r["id"]))

    monkeypatch.setattr(server, "CAPTURE_FAILURES", False)
    run()
    assert not (tmp_path / "failures").exists()
    monkeypatch.setattr(server, "CAPTURE_FAILURES", True)
    run()
    (_, case), = failures.load_all(tmp_path)
    assert case["wrong"] == ["J"]
    logged = " ".join(x["msg"] for x in server.logs.tail(20))
    assert "failure case saved: wrong J" in logged and str(case["truth"]["fl_mm"]) not in logged  # letters only in logs


def test_classify_failure_kinds():
    from failure_report import classify
    truth = dict(bpd_mm=45.04, hc_mm=169.62, ac_mm=147.83, fl_mm=30.18, bpd_w=19, bpd_d=4)
    assert classify("bpd_mm", None, truth)[0] == "unread"
    assert classify("bpd_mm", 450.4, truth)[0] == "decimal_or_unit"
    assert classify("bpd_mm", 45.64, truth) == ("digit_sub", "0>6")
    assert classify("hc_mm", 169.6, truth)[0] == "digit_dropped"
    assert classify("hc_mm", 1699.62, truth)[0] == "decimal_or_unit"
    assert classify("fl_mm", 147.83, truth)[0] == "other_slot_value"


def test_extract_lines_matches_extract_on_same_lines():
    """The refactor that lets other engines reuse the parser must not change Tesseract results."""
    from usreport.extract import extract_lines, ocr_lines, preprocess
    img, _ = make_sample(8, "cm", False, 0)
    pre = preprocess(img)
    a = extract(img, crosscheck=False)  # Tesseract alone; the default extract() now reads with RapidOCR first
    b = extract_lines([ocr_lines(pre, psm) for psm in (6, 11)], pre=pre)
    assert a["values"] == b["values"] and a["issues"] == b["issues"]
